r"""
Capture per-endpoint perf baselines via django-silk.

Runs a small set of browse flows against the live dev DB (the slimlib
library in ``$CODEX_CONFIG_DIR/codex.sqlite3``), captures the silk
request traces, and writes a JSON artifact.

Runs outside pytest so that requests hit the real (non-rollback) DB and
silk has a stable store to pull from. Requires ``DEBUG=1`` so silk is
installed and capturing.

Usage::

    CODEX_CONFIG_DIR=$HOME/Code/codex/config DEBUG=1 \
        uv run python -m tests.perf.run_baseline \
        --out tasks/browser-views-perf/baseline.json

Each flow runs twice: one warm-up (discarded) and one measured call.
"""

from __future__ import annotations

import argparse
import importlib
import json
import os
import sys
from http import HTTPStatus
from pathlib import Path
from typing import Any

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "codex.settings")
os.environ.setdefault("DEBUG", "1")

# `codex/__init__.py` calls django.setup(); run it as a statement so
# ruff's import sorter can't reorder it below the django imports that
# require apps.populate() to have completed.
importlib.import_module("codex")

from cachalot.api import invalidate as cachalot_invalidate  # noqa: E402
from django.contrib.auth.models import User  # noqa: E402
from django.core.cache import cache as django_cache  # noqa: E402
from django.core.management import call_command  # noqa: E402
from django.db.models import Count  # noqa: E402
from django.test import Client  # noqa: E402

from codex.models import Comic, Series  # noqa: E402

# Silk may not be importable if settings skipped DEBUG — guard early.
try:
    from silk.models import Request as SilkRequest
except ImportError as exc:  # pragma: no cover - dev-only
    msg = "django-silk not installed; set DEBUG=1 and re-run `uv sync`."
    raise SystemExit(msg) from exc


def _ensure_silk_schema() -> None:
    """Apply silk migrations to the silky DB idempotently."""
    call_command("migrate", "silk", database="silky", verbosity=0)


PERF_USER = "codex-perf"
DEFAULT_OUT = Path("tasks/browser-views-perf/baseline.json")


def _get_or_create_perf_user() -> User:
    user, created = User.objects.get_or_create(
        username=PERF_USER,
        defaults={"is_staff": True, "is_superuser": True},
    )
    if created:
        user.set_password("perf-baseline")
        user.save()
    return user


def _busy_series_pk() -> int:
    """Pick a series with the most comics for metadata / filtered flows."""
    row = (
        Series.objects.annotate(n=Count("comic"))
        .filter(n__gte=10)
        .order_by("-n")
        .values("pk", "n")
        .first()
    )
    if not row:
        row = (
            Series.objects.annotate(n=Count("comic"))
            .order_by("-n")
            .values("pk", "n")
            .first()
        )
    if not row:
        msg = "No Series rows in DB; point CODEX_CONFIG_DIR at a populated DB."
        raise SystemExit(msg)
    return int(row["pk"])


def _busy_comic_pk() -> int:
    """Pick the comic with the richest M2M coverage — exercises the metadata detail path."""
    row = (
        Comic.objects.annotate(n=Count("characters"))
        .order_by("-n")
        .values("pk", "n")
        .first()
    )
    if not row:
        msg = "No Comic rows in DB; point CODEX_CONFIG_DIR at a populated DB."
        raise SystemExit(msg)
    return int(row["pk"])


_BROWSE_PLUS_COVERS_URL = "/api/v3/r/0/1"


def _build_flows(series_pk: int, comic_pk: int) -> list[dict[str, Any]]:
    return [
        {
            "name": "flow_a_root_browse",
            "description": "Root browse, no filters, no search.",
            "kind": "url",
            "url": "/api/v3/r/0/1",
        },
        {
            "name": "flow_b_filtered_search",
            "description": "Root browse with a search term.",
            "kind": "url",
            "url": "/api/v3/r/0/1?q=man",
        },
        {
            "name": "flow_c_series_metadata",
            "description": "Metadata detail for the largest series.",
            "kind": "url",
            "url": f"/api/v3/s/{series_pk}/metadata",
        },
        {
            "name": "flow_c2_comic_metadata",
            "description": "Metadata detail for a single rich comic (exercises FK + M2M hydration).",
            "kind": "url",
            "url": f"/api/v3/c/{comic_pk}/metadata",
        },
        {
            "name": "flow_d_browse_plus_covers",
            "description": "Root browse then fetch every returned cover.",
            "kind": "browse_plus_covers",
            "url": _BROWSE_PLUS_COVERS_URL,
        },
        {
            "name": "flow_e_search_plus_covers",
            "description": "Search browse then fetch every returned cover.",
            "kind": "browse_plus_covers",
            "url": f"{_BROWSE_PLUS_COVERS_URL}?q=man",
        },
    ]


def _build_cover_urls(page: dict[str, Any]) -> list[str]:
    """Pick the best cover URL for each card."""
    urls: list[str] = []
    cards = list(page.get("groups") or []) + list(page.get("books") or [])
    for card in cards:
        if custom_pk := card.get("coverCustomPk"):
            urls.append(f"/api/v3/custom_cover/{custom_pk}/cover.webp")
            continue
        if cover_pk := card.get("coverPk"):
            urls.append(f"/api/v3/c/{cover_pk}/cover.webp")
            continue
        # Legacy fallback — group + ids pair.
        group = card.get("group")
        ids = card.get("ids") or []
        if group and ids:
            pk_list = ",".join(str(p) for p in ids)
            urls.append(f"/api/v3/{group}/{pk_list}/cover.webp")
    return urls


def _aggregate_traces(traces) -> dict[str, Any]:
    """Sum silk counters across a set of traces."""
    total_sql = sum(int(t.num_sql_queries or 0) for t in traces)
    total_ms = sum(float(t.time_taken or 0) for t in traces)
    return {
        "num_requests": len(traces),
        "total_sql_queries": total_sql,
        "total_time_ms": total_ms,
    }


def _capture_browse_plus_covers(client: Client, url: str) -> dict[str, Any]:
    """
    Flow D: one browse request, then fetch every returned cover.

    Mirrors what the browser does when a user lands on a browse page —
    one JSON request for the card list followed by a parallel fan-out
    over every card's cover URL. The assistant used to pay the full
    group-resolution pipeline 72x per page; the cover annotation +
    per-pk endpoint should collapse that to one cheap ACL probe per
    cover.
    """
    path_prefix = "/api/v3/"
    SilkRequest.objects.filter(path__startswith=path_prefix).delete()
    django_cache.clear()
    cachalot_invalidate()

    def _one_pass():
        SilkRequest.objects.filter(path__startswith=path_prefix).delete()
        browse_response = client.get(url)
        if browse_response.status_code != HTTPStatus.OK:
            return None, browse_response, []
        payload = browse_response.json()
        cover_urls = _build_cover_urls(payload)
        for cover_url in cover_urls:
            client.get(cover_url)
        traces = list(
            SilkRequest.objects.filter(path__startswith=path_prefix).order_by(
                "start_time"
            )
        )
        return payload, browse_response, traces

    _, cold_response, cold_traces = _one_pass()
    cold = {"status_code": cold_response.status_code}
    cold.update(_aggregate_traces(cold_traces))

    _, warm_response, warm_traces = _one_pass()
    warm = {"status_code": warm_response.status_code}
    warm.update(_aggregate_traces(warm_traces))

    return {"cold": cold, "warm": warm}


def _capture(client: Client, url: str) -> dict[str, Any]:
    """
    Run one request, pull the most-recent silk trace.

    Runs twice: cold (cachalot invalidated) and warm (populated). The
    cold pass is the baseline we track — it reflects user-facing latency
    on cache misses, which is what the perf work targets.
    """
    path_prefix = url.split("?", 1)[0]
    SilkRequest.objects.filter(path__startswith=path_prefix).delete()

    # `cache_page` on browser URLs stores the full response in the
    # default cache; cachalot caches QuerySet results. Wipe both so the
    # cold pass actually hits the view and the DB.
    django_cache.clear()
    cachalot_invalidate()
    cold_response = client.get(url)
    cold_trace = (
        SilkRequest.objects.filter(path__startswith=path_prefix)
        .order_by("-start_time")
        .first()
    )

    SilkRequest.objects.filter(path__startswith=path_prefix).delete()
    warm_response = client.get(url)
    warm_trace = (
        SilkRequest.objects.filter(path__startswith=path_prefix)
        .order_by("-start_time")
        .first()
    )

    def _summarize(trace, response):
        if trace is None:
            return {
                "status_code": response.status_code,
                "error": "no silk trace captured",
            }
        return {
            "status_code": response.status_code,
            "num_sql_queries": trace.num_sql_queries,
            "time_taken_ms": float(trace.time_taken or 0),
        }

    return {
        "cold": _summarize(cold_trace, cold_response),
        "warm": _summarize(warm_trace, warm_response),
    }


def _reset_user_settings(client: Client) -> None:
    """
    Clear SettingsBrowser for the perf user.

    Flows share a user, and ``?q=foo`` on one flow persists to
    SettingsBrowser. Without a reset, subsequent flows pick up the
    previous flow's search — which makes A + B indistinguishable and
    tanks cold numbers on the correlated cover subquery with a leftover
    FTS match.
    """
    client.delete("/api/v3/r/settings")


def run(out_path: Path) -> int:
    """Run all flows and write the baseline artifact to ``out_path``."""
    _ensure_silk_schema()
    user = _get_or_create_perf_user()
    client = Client()
    client.force_login(user)

    series_pk = _busy_series_pk()
    comic_pk = _busy_comic_pk()
    flows = _build_flows(series_pk, comic_pk)

    # Warm-up pass.
    for flow in flows:
        client.get(flow["url"])

    results: list[dict[str, Any]] = []
    for flow in flows:
        _reset_user_settings(client)
        if flow.get("kind") == "browse_plus_covers":
            sample = _capture_browse_plus_covers(client, flow["url"])
        else:
            sample = _capture(client, flow["url"])
        results.append({**flow, **sample})

    artifact = {
        "series_pk_used": series_pk,
        "comic_pk_used": comic_pk,
        "flows": results,
    }
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(artifact, indent=2, default=str))
    sys.stdout.write(f"Wrote baseline to {out_path}\n")

    def _row_sql(sample: dict[str, Any]) -> Any:
        return sample.get("num_sql_queries", sample.get("total_sql_queries", "?"))

    def _row_ms(sample: dict[str, Any]) -> float:
        return float(sample.get("time_taken_ms", sample.get("total_time_ms", 0)))

    for row in results:
        cold = row.get("cold", {})
        warm = row.get("warm", {})
        result = (
            f"  {row['name']:30s}  "
            f"cold: sql={_row_sql(cold):>4}  "
            f"wall={_row_ms(cold):>8.2f}ms  |  "
            f"warm: sql={_row_sql(warm):>4}  "
            f"wall={_row_ms(warm):>8.2f}ms\n"
        )
        sys.stdout.write(result)
    return 0


def main() -> int:
    """Parse CLI args and dispatch to :func:`run`."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--out",
        type=Path,
        default=DEFAULT_OUT,
        help=f"Output JSON path (default: {DEFAULT_OUT})",
    )
    args = parser.parse_args()
    return run(args.out)


if __name__ == "__main__":
    raise SystemExit(main())

r"""
Capture per-endpoint OPDS perf baselines via django-silk.

Sibling to ``tests/perf/run_baseline.py`` but targets the OPDS surface.
Runs the same cold-then-warm methodology against the live dev DB and
writes a JSON artifact that mirrors the browser baseline shape.

OPDS authenticates via Basic, Bearer, or Session. The harness uses
Session (``Client.force_login``) — same as the browser harness — which
exercises the same view-side code path that interactive browser
sessions use. Per-auth-class measurement (Basic with HTTP_AUTHORIZATION
header) is left for a follow-up if traffic data shows Basic dominates.

Usage::

    CODEX_CONFIG_DIR=$HOME/Code/codex/config DEBUG=1 \
        uv run python -m tests.perf.run_opds_baseline \
        --out tasks/opds-views-perf/baseline.json

Each flow runs twice: one cold (cachalot + django_cache invalidated)
and one warm (post-cold). Cold is the number we track because OPDS
clients on cold-start (or after a librarian-driven invalidation) pay
the cold cost on every navigation step.
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
DEFAULT_OUT = Path("tasks/opds-views-perf/baseline.json")
# OPDS GET endpoints can legally return 200 (full payload), 204 (no
# content — e.g. progression GET when no bookmark exists), or 302
# (catalog redirects). Treat all three as a successful exercise of the
# view code rather than an error.
_OK_STATUS_CODES = frozenset({HTTPStatus.OK, HTTPStatus.NO_CONTENT, HTTPStatus.FOUND})
# OPDS path prefix — silk filters on this so traces from non-OPDS
# requests (e.g. silk's own admin pages) don't pollute the trace pool.
_OPDS_PATH_PREFIX = "/opds/"


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
    """Pick a series with the most comics for feed-deep / acquisition flows."""
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
    """Pick the comic with the richest M2M coverage — exercises manifest credits + subjects."""
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


def _build_flows(series_pk: int, comic_pk: int) -> list[dict[str, Any]]:
    """
    Define the OPDS perf flows.

    Every flow on the v1 + v2 feed surface plus the static auth /
    opensearch docs. Progression PUT is omitted because it mutates
    state; if PUT volume turns out to dominate (sub-plan 06 #1), add a
    seeded-bookmark variant in a follow-up.
    """
    return [
        {
            "name": "v1_start",
            "description": "v1 OPDS root (Atom navigation feed at /opds/v1.2/).",
            "kind": "url",
            "url": "/opds/v1.2/",
        },
        {
            "name": "v1_root_browse",
            "description": "v1 root browse (Atom feed at the canonical group URL).",
            "kind": "url",
            "url": "/opds/v1.2/r/0/1",
        },
        {
            "name": "v1_series_acquisition",
            "description": (
                "v1 acquisition feed for the busiest series — exercises the "
                "per-entry stream / download / cover link generation in "
                "v1/entry/links.py. ``topGroup=s`` is required because the "
                "between-flow settings reset defaults topGroup to ``p`` "
                "(Publisher) and ``s/325/1`` would 302 to root otherwise."
            ),
            "kind": "url",
            "url": f"/opds/v1.2/s/{series_pk}/1?topGroup=s",
        },
        {
            "name": "v1_acquisition_with_metadata",
            "description": (
                "v1 acquisition feed with ?opdsMetadata=1 — fires the 9-query "
                "M2M fan-out (authors / contributors / category_groups) per "
                "entry. Headline number for sub-plan 03 #1."
            ),
            "kind": "url",
            "url": f"/opds/v1.2/s/{series_pk}/1?topGroup=s&opdsMetadata=1",
        },
        {
            "name": "v1_opensearch",
            "description": "Static opensearch description doc (sub-plan 06 #5).",
            "kind": "url",
            "url": "/opds/v1.2/opensearch/v1.1",
        },
        {
            "name": "v2_start",
            "description": (
                "v2 OPDS start page at /opds/v2.0 — fires the preview-pipeline "
                "rerun for every PREVIEW_GROUPS link spec (sub-plan 02 #2)."
            ),
            "kind": "url",
            "url": "/opds/v2.0",
        },
        {
            "name": "v2_root_browse",
            "description": "v2 JSON feed at the root group URL.",
            "kind": "url",
            "url": "/opds/v2.0/r/0/1",
        },
        {
            "name": "v2_series_publications",
            "description": (
                "v2 publications feed for the busiest series — per-publication "
                "_thumb / link assembly hot path. ``topGroup=s`` for the same "
                "reason as v1_series_acquisition."
            ),
            "kind": "url",
            "url": f"/opds/v2.0/s/{series_pk}/1?topGroup=s",
        },
        {
            "name": "v2_manifest",
            "description": (
                "v2 single-comic manifest. Headline number for sub-plan 05: "
                "11-query credit fan-out + 7-query M2M subject loop + "
                "story_arcs N+1 + per-page reading_order reverse() calls."
            ),
            "kind": "url",
            "url": f"/opds/v2.0/c/{comic_pk}/1",
        },
        {
            "name": "v2_progression_get",
            "description": (
                "Progression GET for the busiest comic. Returns 204 when the "
                "test user has no bookmark — still exercises the ACL filter + "
                "FilteredRelation annotation pipeline (sub-plan 06 #2)."
            ),
            "kind": "url",
            "url": f"/opds/v2.0/c/{comic_pk}/position",
        },
        {
            "name": "auth_doc_v1",
            "description": "Static OPDS authentication document (sub-plan 06 #5).",
            "kind": "url",
            "url": "/opds/auth/v1",
        },
    ]


def _aggregate_traces(traces) -> dict[str, Any]:
    """Sum silk counters across a set of traces."""
    total_sql = sum(int(t.num_sql_queries or 0) for t in traces)
    total_ms = sum(float(t.time_taken or 0) for t in traces)
    return {
        "num_requests": len(traces),
        "total_sql_queries": total_sql,
        "total_time_ms": total_ms,
    }


def _capture(client: Client, url: str) -> dict[str, Any]:
    """
    Run one request twice, pull the most-recent silk trace each time.

    Cold-then-warm. Cold pass clears django_cache + cachalot before the
    request so the view runs against an empty cache. Warm pass runs
    immediately after to capture the cached-path number, which acts as
    the lower bound (= cache lookup cost only).
    """
    path_prefix = url.split("?", 1)[0]
    SilkRequest.objects.filter(path__startswith=path_prefix).delete()

    # `cache_page` on browser URLs stores the full response in the
    # default cache; cachalot caches QuerySet results. Wipe both so the
    # cold pass actually hits the view and the DB. (`cache_page` is a
    # no-op on OPDS today because OPDS_TIMEOUT=0, but wiping is cheap
    # and keeps the harness valid if we re-enable.)
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
    Clear browser SettingsBrowser between flows.

    OPDSBrowserView extends BrowserView and persists params to
    SettingsBrowser per-request. ``?opdsMetadata=1`` and similar
    flags would otherwise carry over to the next flow — the same bug
    that bit ``run_baseline.py`` and required this same reset. Reuse
    the browser settings DELETE endpoint; it's user-scoped and OPDS
    settings live in the same row.
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

    # Warm-up pass — populates module-level caches, primes any one-time
    # imports / URL-pattern resolutions, etc.
    for flow in flows:
        client.get(flow["url"])

    results: list[dict[str, Any]] = []
    for flow in flows:
        _reset_user_settings(client)
        sample = _capture(client, flow["url"])
        results.append({**flow, **sample})

    artifact = {
        "series_pk_used": series_pk,
        "comic_pk_used": comic_pk,
        "flows": results,
    }
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(artifact, indent=2, default=str))
    sys.stdout.write(f"Wrote OPDS baseline to {out_path}\n")

    def _row_sql(sample: dict[str, Any]) -> Any:
        return sample.get("num_sql_queries", sample.get("total_sql_queries", "?"))

    def _row_ms(sample: dict[str, Any]) -> float:
        return float(sample.get("time_taken_ms", sample.get("total_time_ms", 0)))

    for row in results:
        cold = row.get("cold", {})
        warm = row.get("warm", {})
        # Surface unexpected statuses (5xx, 401/403) so they don't hide
        # in the JSON. 200/204/302 are all valid OPDS responses.
        for sample_name, sample in (("cold", cold), ("warm", warm)):
            status = sample.get("status_code")
            if status is not None and status not in _OK_STATUS_CODES:
                sys.stdout.write(
                    f"  ! {row['name']:30s}  {sample_name} status={status}\n"
                )
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

r"""
Capture per-endpoint reader perf baselines via django-silk.

Sibling to ``tests/perf/run_baseline.py`` and ``run_opds_baseline.py``.
Mirrors the cold-then-warm methodology against the live dev DB and
writes a JSON artifact in the same shape.

The reader surface authenticates via DRF Session auth on
``c/<pk>`` and ``c/<pk>/settings``, plus the page-binary endpoint
``c/<pk>/<page>/page.jpg`` (cookie-authenticated, ACL-filtered).
The harness uses Session (``Client.force_login``) — same as the
browser / OPDS harnesses — which exercises the same view-side code
path that interactive sessions use.

Usage::

    CODEX_CONFIG_DIR=$HOME/Code/codex/config DEBUG=1 \
        uv run python -m tests.perf.run_reader_baseline \
        --out tasks/reader-views-perf/baseline.json

Each flow runs twice: one cold (cachalot + django_cache invalidated)
and one warm (post-cold). Cold is the tracked metric because
real-world reader hits land on cold pipeline state once a comic is
opened (``c/<pk>``) or after a librarian-driven invalidation; the
warm pass acts as a lower-bound reading.

Out of scope (matches the reader perf plan):

- Page-extraction internals (Comicbox archive open variance).
- Frontend prefetch behavior.
- Multi-worker shared cache shape.
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
from codex.views.reader._archive_cache import (  # noqa: E402
    archive_cache,
    page_acl_cache,
)

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
DEFAULT_OUT = Path("tasks/reader-views-perf/baseline.json")
# Reader endpoints return 200 (full payload) on a happy path. 302
# would surface a misconfigured ACL / settings drift; 404 surfaces
# missing comic paths on disk. Both are flagged loudly so they
# don't hide silently in the JSON artifact.
_OK_STATUS_CODES = frozenset({HTTPStatus.OK})
# Reader path prefix — silk's path filter scopes traces to reader
# requests only so non-reader noise (silk's own admin pages) doesn't
# pollute the trace pool.
_READER_PATH_PREFIX = "/api/v3/c/"


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
    """Pick a series with the most comics — exercises the prev/curr/next iteration worst case."""
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


def _busy_series_comic_pk(series_pk: int) -> int:
    """
    Pick a mid-arc comic from the busiest series.

    The middle issue of a large series is the worst case for
    ``get_book_collection``'s prev/curr/next iteration: ~50% of the
    arc is materialized to find both the previous and current rows
    (sub-plan 01 #1).
    """
    pks = list(
        Comic.objects.filter(series_id=series_pk)
        .order_by("issue_number", "issue_suffix", "pk")
        .values_list("pk", flat=True)
    )
    if not pks:
        msg = f"No Comics in series {series_pk}."
        raise SystemExit(msg)
    return int(pks[len(pks) // 2])


def _busy_comic_pk() -> int:
    """Pick the comic with the richest M2M coverage (mirror of OPDS harness)."""
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


def _high_page_comic_pk() -> int:
    """
    Pick the comic with the highest page_count.

    Used by the page-endpoint flows to exercise per-page extraction
    against a realistic mid-comic page index. A 1-page comic doesn't
    distinguish first / middle / last hits.
    """
    row = (
        Comic.objects.filter(page_count__gte=20)
        .order_by("-page_count")
        .values("pk", "page_count")
        .first()
    )
    if not row:
        row = Comic.objects.order_by("-page_count").values("pk", "page_count").first()
    if not row:
        msg = "No Comic rows in DB."
        raise SystemExit(msg)
    return int(row["pk"])


def _build_flows(
    comic_pk: int,
    busy_series_comic_pk: int,
    high_page_pk: int,
    high_page_count: int,
) -> list[dict[str, Any]]:
    """
    Define the reader perf flows.

    - Reader endpoint (``c/<pk>``) cold + warm.
    - Settings GET (single + multi-scope).
    - Page binary (first / middle / no-bookmark variants).

    Page-binary flows hit the comic file on disk via Comicbox; the
    archive-open cost dominates wall time on those rows. The first
    / middle / no-bookmark split is intended to surface (a) the
    archive-open cost, (b) any per-page-index variance, and (c) the
    cost of the bookmark-update task enqueue (suppressed via
    ``?bookmark=0``).
    """
    middle_page = max(1, high_page_count // 2)
    return [
        {
            "name": "reader_open",
            "description": (
                "Reader endpoint for the busiest comic (richest M2M coverage). "
                "Hits the params / arcs / books / reader inheritance chain — "
                "the prev/curr/next window builder is the hot path here "
                "(sub-plan 01 #1)."
            ),
            "kind": "url",
            "url": f"/api/v3/c/{comic_pk}",
        },
        {
            "name": "reader_open_large_arc",
            "description": (
                "Reader endpoint for a comic inside the busiest series — "
                "specifically the middle issue, which is the worst case for "
                "``get_book_collection``'s prev/curr/next iteration "
                "(sub-plan 01 #1)."
            ),
            "kind": "url",
            "url": f"/api/v3/c/{busy_series_comic_pk}",
        },
        {
            "name": "settings_global",
            "description": "Reader settings GET — global scope only.",
            "kind": "url",
            "url": "/api/v3/c/settings?scopes=g",
        },
        {
            "name": "settings_multiscope",
            "description": (
                "Reader settings GET — global + series + comic scopes. Each "
                "non-trivial scope fires its own query plus a name lookup "
                "(sub-plan 02 #1)."
            ),
            "kind": "url",
            "url": f"/api/v3/c/{comic_pk}/settings?scopes=g,s,c",
        },
        {
            "name": "page_first",
            "description": (
                "Page binary GET for page 0 of the high-page-count comic. "
                "Exercises the Comicbox archive open + first-page extraction "
                "+ bookmark-update task enqueue (sub-plan 03 #1)."
            ),
            "kind": "url",
            "url": f"/api/v3/c/{high_page_pk}/0/page.jpg",
        },
        {
            "name": "page_middle",
            "description": (
                "Page binary GET for a middle page of the high-page-count "
                "comic — exercises the same archive open as page_first; "
                "wall-time difference reflects per-page extraction variance."
            ),
            "kind": "url",
            "url": f"/api/v3/c/{high_page_pk}/{middle_page}/page.jpg",
        },
        {
            "name": "page_no_bookmark",
            "description": (
                "Page binary GET with ``?bookmark=0`` — same archive open "
                "as page_first but skips the librarian-queue enqueue. The "
                "wall-time delta vs. page_first reflects task-queue "
                "overhead (sub-plan 03 #3)."
            ),
            "kind": "url",
            "url": f"/api/v3/c/{high_page_pk}/0/page.jpg?bookmark=0",
        },
    ]


def _capture(client: Client, url: str) -> dict[str, Any]:
    """
    Run one request twice, pull the most-recent silk trace each time.

    Cold-then-warm. Cold pass clears django_cache + cachalot AND the
    reader's process-local archive / ACL caches before the request so
    the view runs against truly empty cache state. Warm pass runs
    immediately after to capture the cached-path number — the ACL
    cache and archive cache have been populated by the cold call so
    the warm pass exercises the cache-hit path.

    The reader page endpoint has only ``cache_control`` HTTP headers
    (no server-side ``cache_page``); the in-process ACL + archive
    caches are what amortize the cold cost (sub-plan 03 #1, #2).
    """
    # Clear the in-process reader caches so the harness's "cold" pass
    # is a true cold-cache measurement, not a warm-up-loop carryover.
    archive_cache.shutdown()
    page_acl_cache.clear()

    path_prefix = url.split("?", 1)[0]
    SilkRequest.objects.filter(path__startswith=path_prefix).delete()

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

    The reader chain calls ``save_params_to_settings`` from the
    ``params`` property, persisting per-request arc state. Without a
    reset between flows the previous request's settings poison the
    next one's params. Reuse the browser settings DELETE endpoint;
    it's user-scoped and reader settings live in the same row.
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
    busy_series_comic_pk = _busy_series_comic_pk(series_pk)
    high_page_pk = _high_page_comic_pk()
    high_page_count = (
        Comic.objects.filter(pk=high_page_pk)
        .values_list("page_count", flat=True)
        .first()
        or 1
    )
    flows = _build_flows(
        comic_pk, busy_series_comic_pk, high_page_pk, int(high_page_count)
    )

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
        "busy_series_comic_pk_used": busy_series_comic_pk,
        "high_page_pk_used": high_page_pk,
        "high_page_count": int(high_page_count),
        "flows": results,
    }
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(artifact, indent=2, default=str))
    sys.stdout.write(f"Wrote reader baseline to {out_path}\n")

    def _row_sql(sample: dict[str, Any]) -> Any:
        return sample.get("num_sql_queries", "?")

    def _row_ms(sample: dict[str, Any]) -> float:
        return float(sample.get("time_taken_ms", 0))

    for row in results:
        cold = row.get("cold", {})
        warm = row.get("warm", {})
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

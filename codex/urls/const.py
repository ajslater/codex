"""Timeouts."""

COMMON_TIMEOUT = 60 * 60
BROWSER_TIMEOUT = 60 * 5
COVER_MAX_AGE = 60 * 60 * 24 * 7
PAGE_MAX_AGE = COVER_MAX_AGE
# 60 s — long enough to amortize the full feed pipeline across a tab
# refresh / reader app re-fetch, short enough that bookmark-position
# changes show up before the next poll. Per-route ``vary_on_headers``
# scopes the cache key so per-user feeds don't leak across sessions
# (sub-plan 01 #1). Was previously 0 (cache_page no-op) for an
# unattributed reason — the disable rationale is reconstructed in
# tasks/opds-views-perf/stage0.md.
OPDS_TIMEOUT = 60

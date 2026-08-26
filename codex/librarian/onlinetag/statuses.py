"""
The per-comic status vocabulary for an online tagging scan.

These strings are the wire contract with the admin Tagging tab's status
table: they reach the frontend verbatim (the camelCase renderer rewrites dict
*keys*, never values), so the frontend matches on these exact literals.

They live in their own dependency-free module because both ends of the
pipeline need them — :mod:`~codex.librarian.onlinetag.outcome_stats` folds
events into them and :mod:`~codex.librarian.onlinetag.session_snapshot`
renders them — and importing one from the other would close a cycle.
"""

from __future__ import annotations

from typing import Final

QUEUED: Final = "queued"
IN_FLIGHT: Final = "in_flight"
MATCHED: Final = "matched"
NO_MATCH: Final = "no_match"
NEEDS_REVIEW: Final = "needs_review"
ERROR: Final = "error"
# Per-source only: this source is throttled and the lookup is sitting out its
# retry wait. The file-level status stays in_flight — the comic *is* being
# worked on, just not right this second.
WAITING: Final = "waiting"
# Outcomes of admin match-review actions. A scan never produces these; they are
# overlaid at read time from the resolution record so a comic the admin picked
# or skipped no longer reads as still "needs review".
USER_MATCHED: Final = "user_matched"
USER_SKIPPED: Final = "user_skipped"

# Display ordering buckets: actionable first, then upcoming, then finished.
ACTIONABLE: Final = (IN_FLIGHT, NEEDS_REVIEW, ERROR)
FINISHED: Final = (MATCHED, NO_MATCH)
# Per-source cell values that only make sense while a scan is running.
LIVE_SOURCE_STATUSES: Final = (IN_FLIGHT, WAITING)

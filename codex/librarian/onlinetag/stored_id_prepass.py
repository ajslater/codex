"""
Resolve already-identified comics by their stored online id before searching.

A bulk online-tag scan otherwise hands every comic to comicbox's search path,
which resolves the series by name and lists issues per candidate series — many
API calls per comic. Comics codex already holds a Metron / Comic Vine *issue*
id for (in the ``Identifier`` table) need none of that: fetching that one issue
by explicit id is a single API call. Reading the id straight from the database
also covers comics whose id never round-tripped into the file. Callers use this
to fetch those issues by id and hand them to the same write path the scan uses,
leaving only the unidentified comics for the search session.
"""

from __future__ import annotations

import re
from typing import TYPE_CHECKING

from codex.models.identifier import Identifier, IdentifierType

if TYPE_CHECKING:
    from collections.abc import Collection

# Comic Vine keys may be stored long-form (``4000-12345``); the issue id is the
# trailing integer. Metron keys are already bare integers.
_TRAILING_INT_RE = re.compile(r"(\d+)$")


def _parse_issue_id(key: str | None) -> int | None:
    """Pull the trailing integer issue id out of a stored identifier key."""
    match = _TRAILING_INT_RE.search(key or "")
    return int(match.group(1)) if match else None


def build_stored_id_map(
    comic_pks: Collection[int], sources: tuple[str, ...]
) -> dict[int, dict[str, int]]:
    """
    Map ``comic pk -> {source: issue_id}`` from stored issue identifiers.

    Only the requested ``sources`` and issue-level identifiers are considered.
    Each comic's sources are ordered by the caller's source priority so the
    first entry is the primary source to fetch.
    """
    if not comic_pks or not sources:
        return {}
    rows = Identifier.objects.filter(
        comic__pk__in=comic_pks,
        id_type=IdentifierType.ISSUE.value,
        source__name__in=sources,
    ).values_list("comic__pk", "source__name", "key")

    priority = {source: i for i, source in enumerate(sources)}
    id_map: dict[int, dict[str, int]] = {}
    for pk, source_name, key in rows:
        issue_id = _parse_issue_id(key)
        if issue_id is None:
            continue
        id_map.setdefault(pk, {})[source_name] = issue_id
    # Re-order each comic's sources by priority so the primary pick is stable.
    return {
        pk: dict(sorted(srcs.items(), key=lambda kv: priority.get(kv[0], len(sources))))
        for pk, srcs in id_map.items()
    }

"""
Fetch comic metadata by a known online issue id (comicbox explicit-id tagging).

Codex's online tagging normally *searches* a source by filename and ranks
candidates. When the operator already knows the exact Metron / Comic Vine issue
id, this module drives comicbox's explicit-id path instead
(``online.lookup.ids``), which skips the search entirely and calls
``source.get(issue_id)`` for that one issue. It mirrors the per-file flow of
``comicbox.online_session.OnlineSession._run_one`` minus the selector — an
explicit-id fetch never reaches the matcher, so it never prompts.
"""

from __future__ import annotations

import re
from dataclasses import replace
from typing import TYPE_CHECKING, Any

from comicbox.box import Comicbox
from comicbox.config import get_config
from comicbox.config.settings import (
    MatchMode,
    OnlineAuthSettings,
    OnlineLookupSettings,
    OnlineSourceCredentials,
    Prompts,
)
from comicbox.formats.comicbox.schema import IDENTIFIERS_KEY
from comicbox.identifiers import ID_KEY_KEY

if TYPE_CHECKING:
    from pathlib import Path

    from comicbox.config.settings import ComicboxSettings
    from comicbox.online_session import OnlineCredentials

# Comic Vine keys may be stored long-form (``4000-67890``); the issue id is the
# trailing integer. Metron keys are already bare integers.
_TRAILING_INT_RE = re.compile(r"(\d+)$")


def _build_auth_source(
    source: str, credentials: OnlineCredentials
) -> OnlineSourceCredentials:
    """Map codex credentials onto comicbox's per-source auth for one source."""
    if source == "metron":
        return OnlineSourceCredentials(
            user=credentials.metron_user,
            password=credentials.metron_password,
            url=credentials.metron_url,
        )
    return OnlineSourceCredentials(
        key=credentials.comicvine_key,
        url=credentials.comicvine_url,
    )


def build_explicit_id_config(
    source: str,
    issue_id: int,
    credentials: OnlineCredentials,
    extra_ids: tuple[tuple[str, int], ...] = (),
) -> ComicboxSettings:
    """
    Build comicbox settings that fetch one or more issues by explicit id.

    Layered as ``replace`` over the defaults exactly like
    ``OnlineSession._build_config`` — but with ``online.lookup.ids`` set so
    comicbox skips the search and calls ``source.get(issue_id)`` directly.
    ``prompts=NEVER`` because the explicit-id path never reaches the matcher.

    When ``extra_ids`` is given (the "merge all sources" path), each
    ``(source, issue_id)`` is also pinned. comicbox always runs every source
    that carries an explicit id, so all are fetched and merged into one record;
    the primary ``source`` is listed first and wins per-field conflicts.
    """
    base = get_config()
    # Primary source first (highest merge priority), then the extra pinned
    # sources; dedup keeps the primary's id if a source repeats.
    ids = {source: issue_id}
    for extra_source, extra_id in extra_ids:
        ids.setdefault(extra_source, extra_id)
    sources = tuple(ids)
    auth_sources = {s: _build_auth_source(s, credentials) for s in sources}
    lookup = OnlineLookupSettings(
        enabled=True,
        sources=sources,
        ids=ids,
        match=MatchMode.AUTO,
        prompts=Prompts.NEVER,
        first_wins=len(sources) <= 1,
    )
    auth = OnlineAuthSettings(sources=auth_sources)
    return replace(base, online=replace(base.online, lookup=lookup, auth=auth))


def _result_has_requested_id(tags: dict[str, Any], source: str, issue_id: int) -> bool:
    """
    Whether the fetched metadata carries ``source``'s id matching ``issue_id``.

    comicbox swallows a failed ``source.get(issue_id)`` (a wrong or unknown id)
    and emits no event, leaving ``to_dict()`` holding only the comic's existing
    metadata. Confirming the returned identifier for ``source`` matches the
    requested id distinguishes a real fetch from "nothing changed" — and rejects
    a wrong id even on an already-tagged comic, whose stale id won't match.
    """
    id_obj = (tags.get(IDENTIFIERS_KEY) or {}).get(source) or {}
    key = id_obj.get(ID_KEY_KEY)
    if not key:
        return False
    match = _TRAILING_INT_RE.search(str(key))
    return bool(match) and int(match.group(1)) == issue_id


def fetch_tags_by_explicit_id(
    path: Path,
    source: str,
    issue_id: int,
    credentials: OnlineCredentials,
    extra_ids: tuple[tuple[str, int], ...] = (),
) -> dict[str, Any] | None:
    """
    Fetch one issue's metadata by explicit id, or ``None`` if it didn't resolve.

    Returns the comicbox-shaped tag dict ready to hand to ``BulkTagWriteTask``.
    With ``extra_ids`` the other sources are also fetched by explicit id and
    merged in. Resolution is keyed on the primary ``source``: an ``extra_ids``
    entry that doesn't resolve simply contributes nothing to the merge.
    """
    # Drop any extra entry for the primary source; it always runs id-pinned.
    extra_ids = tuple((s, i) for s, i in extra_ids if s != source)
    settings = build_explicit_id_config(source, issue_id, credentials, extra_ids)
    with Comicbox(path, config=settings) as cb:
        cb.run_online_lookup()
        payload = cb.to_dict()
    tags = payload.get("comicbox") or {}
    if not _result_has_requested_id(tags, source, issue_id):
        return None
    return tags

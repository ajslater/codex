"""
Extract the numeric issue id from a stored online identifier key.

Comic Vine issue keys are stored long-form (``4000-12345``); comicbox owns the
canonical rule for that ``<type>-<key>`` shape (``PARSE_COMICVINE_RE``), so we
consume it here instead of hand-rolling the format. Metron keys are already
bare integers. Anything else yields ``None`` — the callers (stored-id prepass,
explicit-id confirmation) treat that as "not resolvable", which safely falls
back to search or rejects the id rather than guessing a wrong one.
"""

from comicbox.identifiers import PARSE_COMICVINE_RE


def parse_issue_id(key: str | None) -> int | None:
    """Return the numeric issue id from a stored identifier key, or ``None``."""
    if not key:
        return None
    key = str(key)
    if match := PARSE_COMICVINE_RE.search(key):
        return int(match.group("id_key"))
    return int(key) if key.isdigit() else None

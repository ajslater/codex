"""
Parse user-supplied comic identifiers into a ``(source, issue id)`` pair.

Two entry points share comicbox's identifier knowledge:

- :func:`parse_identifier_url` matches a comic source URL by domain (the
  ``identifier-url`` admin endpoint).
- :func:`parse_identifier_input` accepts the free-form value the "tag by id"
  feature takes — a URL, a ``source:id`` pair, a bare Comic Vine ``4000-NNN``
  code, or a bare integer — and resolves it to a numeric issue id.

Only the supported online sources (``onlinetag.sources``) support id tagging,
so non-issue resource types and other sources are rejected with
operator-facing messages.
"""

from collections.abc import Sequence
from typing import Final

from comicbox.identifiers import PARSE_COMICVINE_RE
from comicbox.identifiers.identifiers import IDENTIFIER_PARTS_MAP

from codex.librarian.onlinetag.credential_validator import KNOWN_SOURCES
from codex.librarian.onlinetag.sources import SOURCES, SUPPORTED_SOURCES

# comicbox maps Comic Vine's 4-digit resource code to a type name; an issue is
# "issue" (code 4000). Volumes/series/etc. are not taggable issue ids.
_ISSUE_TYPE = "issue"
_CV_ISSUE_CODE = "4000"
# Default for ``configured_sources`` — hoisted out of the signature so the
# empty-frozenset construction isn't a call in a parameter default.
_NO_SOURCES: frozenset[str] = frozenset()


def _joined(words: Sequence[str], conjunction: str) -> str:
    """Join ``words`` as prose: ``a or b``, ``a, b, or c``."""
    if len(words) <= 2:  # noqa: PLR2004
        return f" {conjunction} ".join(words)
    return f"{', '.join(words[:-1])}, {conjunction} {words[-1]}"


# The supported sources as the messages below name them: "Metron or Comic
# Vine", "metron or comicvine", "metron:ID / comicvine:ID".
_LABELS: Final = tuple(SOURCES[name].label for name in SUPPORTED_SOURCES)
_ANY_LABEL: Final = _joined(_LABELS, "or")
_EVERY_LABEL: Final = _joined(_LABELS, "and")
_ANY_NAME: Final = _joined(SUPPORTED_SOURCES, "or")
_PREFIXES: Final = " / ".join(f"{name}:ID" for name in SUPPORTED_SOURCES)


def parse_identifier_url(url: str) -> tuple[str, str, str] | None:
    """
    Parse a comic source URL into ``(source, id_type, id_key)``.

    Matches the URL's domain against comicbox's identifier map. Returns
    ``None`` when no known source domain is present or the path won't parse —
    the caller decides whether that's a 400 or a fall-through to other forms.
    """
    url = url.strip()
    if not url:
        return None
    for source_enum, parts in IDENTIFIER_PARTS_MAP.items():
        if parts.domain in url:
            try:
                id_type, id_key = parts.parse_url_path(url)
            except Exception:
                return None
            return source_enum.value, id_type, id_key
    return None


def parse_identifier_input(
    raw: str,
    *,
    source_hint: str | None = None,
    configured_sources: frozenset[str] = _NO_SOURCES,
) -> tuple[str, int]:
    """
    Resolve a free-form identifier to ``(source, issue_id)``.

    Precedence: a source URL (source from the domain), then ``source:id``,
    then a bare Comic Vine ``4000-NNN`` code, then a bare integer — whose
    source comes from ``source_hint`` or, failing that, the sole configured
    source. Raises :class:`ValueError` with an operator-facing message on
    anything unparsable or non-issue.
    """
    raw = (raw or "").strip()
    if not raw:
        msg = f"Enter a {_ANY_LABEL} issue URL or id."
        raise ValueError(msg)

    # 1) A source URL — domain identifies the source.
    if (parsed := parse_identifier_url(raw)) is not None:
        source, id_type, id_key = parsed
        source = _validate_source(source)
        _require_issue_type(source, id_type)
        return source, _coerce_issue_id(source, id_key)

    # 2) Explicit "source:id".
    if ":" in raw:
        prefix, _, value = raw.partition(":")
        source = prefix.strip().lower()
        if source in KNOWN_SOURCES:
            return source, _coerce_issue_id(source, value)
        msg = f"Unknown source {prefix!r}. Use {_ANY_NAME}."
        raise ValueError(msg)

    # 3) A bare Comic Vine 4000-NNN code is self-identifying.
    if PARSE_COMICVINE_RE.fullmatch(raw):
        return "comicvine", _coerce_issue_id("comicvine", raw)

    # 4) A bare integer is ambiguous between the sources.
    if raw.isdigit():
        return _resolve_bare_source(source_hint, configured_sources), int(raw)

    msg = f"Couldn't parse {raw!r} as a {_ANY_LABEL} id."
    raise ValueError(msg)


def _validate_source(source: str) -> str:
    """Reject sources that don't support online id tagging."""
    if source not in KNOWN_SOURCES:
        msg = f"{source.title()} ids aren't supported; only {_EVERY_LABEL}."
        raise ValueError(msg)
    return source


def _require_issue_type(source: str, id_type: str) -> None:
    """Reject volume/series/etc. URLs — only issue ids can tag a comic."""
    if id_type and id_type != _ISSUE_TYPE:
        msg = f"That {source.title()} URL is a {id_type}, not an issue."
        raise ValueError(msg)


def _coerce_issue_id(source: str, value: str) -> int:
    """Coerce a source-specific id value to a numeric issue id."""
    # A URL-derived Metron key keeps its trailing slash (``12345/``); drop it.
    value = value.strip().strip("/")
    if source == "comicvine" and (match := PARSE_COMICVINE_RE.fullmatch(value)):
        code = match.group("id_type")
        if code != _CV_ISSUE_CODE:
            msg = (
                f"Comic Vine {value!r} isn't an issue id "
                f"(resource type {code}, expected {_CV_ISSUE_CODE})."
            )
            raise ValueError(msg)
        return int(match.group("id_key"))
    try:
        return int(value)
    except (TypeError, ValueError) as exc:
        msg = f"{source.title()} needs a numeric issue id; got {value!r}."
        raise ValueError(msg) from exc


def _resolve_bare_source(
    source_hint: str | None, configured_sources: frozenset[str]
) -> str:
    """Pick a source for a bare integer id, or raise if it's ambiguous."""
    if source_hint:
        hint = source_hint.strip().lower()
        if hint in KNOWN_SOURCES:
            return hint
        msg = f"Unknown source {source_hint!r}. Use {_ANY_NAME}."
        raise ValueError(msg)
    known = configured_sources & KNOWN_SOURCES
    if len(known) == 1:
        return next(iter(known))
    msg = (
        f"That id could be {_ANY_LABEL} — paste the issue URL or "
        f"prefix it ({_PREFIXES})."
    )
    raise ValueError(msg)

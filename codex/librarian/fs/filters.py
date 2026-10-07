"""Filter files with regexes."""

import re
from contextlib import suppress
from pathlib import Path

from comicbox.enums.comicbox import FileTypeEnum

# Component-level ignore registry consulted by the poller's walker and
# the watchfiles filter. Either constant can be extended to add new
# patterns without touching the walker/filter call sites:
#
#   _IGNORED_BASENAMES — exact-match basenames (case-sensitive) for
#     OS / archive metadata trees that don't follow a prefix
#     convention: ``@eaDir`` (Synology thumbnails), ``#recycle``
#     (Synology recycle bin), ``__MACOSX`` (Mac archive metadata),
#     ``Thumbs.db`` / ``desktop.ini`` (Windows). Add more here as
#     needed. Skipping these keeps NAS/OS junk out of the library and
#     stops the walker from descending into permission-restricted
#     trees like the recycle bin (issue #795).
#
#   _IGNORED_BASENAME_PREFIXES — prefix matches. Currently catches all
#     hidden files / directories ("." prefix) so VCS metadata (.git),
#     macOS spotlight (.Spotlight-V100), trash (.Trashes), and stray
#     dotfiles (.DS_Store, .nomedia) are skipped wholesale.
#
# A path is ignored when *any* component (relative to its library
# root) matches either rule. The check is applied to every entry the
# walker sees and every event the watcher receives.
_IGNORED_BASENAMES: frozenset[str] = frozenset(
    {
        "@eaDir",  # Synology thumbnail / extended-attribute store
        "#recycle",  # Synology recycle bin
        "__MACOSX",  # macOS archive metadata
        "Thumbs.db",  # Windows thumbnail cache
        "desktop.ini",  # Windows folder settings
    }
)
_IGNORED_BASENAME_PREFIXES: tuple[str, ...] = (".",)


def is_ignored_basename(name: str) -> bool:
    """Return True when ``name`` matches any registered ignore rule."""
    if name in _IGNORED_BASENAMES:
        return True
    return any(name.startswith(prefix) for prefix in _IGNORED_BASENAME_PREFIXES)


def is_ignored_path(path: Path | str, root: Path | str | None = None) -> bool:
    """
    Return True when any component (relative to ``root``) is ignored.

    The check is component-by-component so a hidden ancestor
    (``.git/HEAD``) is caught even when the basename itself is
    innocuous. When ``root`` is provided, components of the root are
    skipped — a library whose path lives under a hidden parent (e.g.
    ``/Users/aj/.archive/comics``) still polls its contents.
    """
    ppath = path if isinstance(path, Path) else Path(path)
    rel = ppath
    if root is not None:
        with suppress(ValueError):
            rel = ppath.relative_to(root)
    return any(is_ignored_basename(part) for part in rel.parts)


_IMAGE_REGEX = r"\.(jpe?g|webp|png|gif|bmp)"
_IMAGE_MATCHER: re.Pattern = re.compile(_IMAGE_REGEX, re.IGNORECASE)

#: Every comic archive suffix, lowercase with its dot, derived from
#: comicbox's file types rather than from what this host can read today.
#: The scan used to leave out CBR and PDF when comicbox said their tool
#: was missing. That made every existing row of that type look deleted
#: to the poller the day unrar went missing, and comicbox 5.3.0's probe,
#: which test-extracts a member, fails on more hosts than the path check
#: it replaced. A comic the host cannot open now fails its import with
#: comicbox's reason instead ("'unrar' not on path"), where the admin
#: can see it, and its row stays.
COMIC_SUFFIXES: frozenset[str] = frozenset(
    f".{file_type.value.lower()}" for file_type in FileTypeEnum
)


def match_comic(path: Path) -> bool:
    """Match comic file."""
    return bool(path and path.suffix) and path.suffix.lower() in COMIC_SUFFIXES


def match_image(path: Path) -> bool:
    """Match image file."""
    return bool(path and path.suffix and _IMAGE_MATCHER.match(path.suffix) is not None)

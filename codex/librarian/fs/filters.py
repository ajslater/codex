"""Filter files with regexes."""

import re
from contextlib import suppress
from pathlib import Path

from comicbox.box import Comicbox
from loguru import logger

from codex.models.paths import CustomCover
from codex.settings import CUSTOM_COVERS_DIR, CUSTOM_COVERS_GROUP_DIRS

# Component-level ignore registry consulted by the poller's walker and
# the watchfiles filter. Either constant can be extended to add new
# patterns without touching the walker/filter call sites:
#
#   _IGNORED_BASENAMES — exact-match basenames (case-sensitive). Use
#     this for OS / archive metadata trees that don't follow a prefix
#     convention. Examples for future extension: ``"@eaDir"``
#     (Synology), ``"__MACOSX"`` (Mac archive metadata), ``"Thumbs.db"``
#     / ``"desktop.ini"`` (Windows), ``"#recycle"`` (recycle bins).
#
#   _IGNORED_BASENAME_PREFIXES — prefix matches. Currently catches all
#     hidden files / directories ("." prefix) so VCS metadata (.git),
#     macOS spotlight (.Spotlight-V100), trash (.Trashes), and stray
#     dotfiles (.DS_Store, .nomedia) are skipped wholesale.
#
# A path is ignored when *any* component (relative to its library
# root) matches either rule. The check is applied to every entry the
# walker sees and every event the watcher receives.
_IGNORED_BASENAMES: frozenset[str] = frozenset()
_IGNORED_BASENAME_PREFIXES: tuple[str, ...] = (".",)


def is_ignored_basename(name: str) -> bool:
    """Return True when ``name`` matches any registered ignore rule."""
    if name in _IGNORED_BASENAMES:
        return True
    if not any(name.startswith(prefix) for prefix in _IGNORED_BASENAME_PREFIXES):
        return False
    # Folder-cover dotfiles (``.codex-cover.jpg`` etc.) are intentional
    # user-supplied covers, not OS noise — the dotfile filter must let
    # them through so the cover predicate downstream can claim them.
    return not match_folder_cover(Path(name))


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


def _build_comic_matcher() -> re.Pattern:
    comic_regex = r"\.(cb[zt7"
    unsupported = []
    if Comicbox.is_unrar_supported():
        comic_regex += r"r"
    else:
        unsupported.append("CBR")
    comic_regex += r"]"

    if Comicbox.is_pdf_supported():
        comic_regex += r"|pdf"
    else:
        unsupported.append("PDF")
    comic_regex += ")$"
    if unsupported:
        un_str = ", ".join(unsupported)
        logger.warning(f"Cannot detect or read from {un_str} archives")
    return re.compile(comic_regex, re.IGNORECASE)


_COMIC_MATCHER: re.Pattern = _build_comic_matcher()


def _match_suffix(pattern: re.Pattern, path: Path) -> bool:
    """Match suffix with pattern."""
    return bool(path and path.suffix and pattern.match(path.suffix) is not None)


def match_comic(path: Path) -> bool:
    """Match comic file."""
    return _match_suffix(_COMIC_MATCHER, path)


def match_image(path: Path) -> bool:
    """Match image file."""
    return _match_suffix(_IMAGE_MATCHER, path)


def match_folder_cover(path: Path) -> bool:
    """Match a folder cover image (e.g. cover.jpg next to comics)."""
    return path.stem == CustomCover.FOLDER_COVER_STEM and match_image(path)


def match_group_cover_image(path: Path) -> bool:
    """Match a custom group cover image in the custom-covers directory."""
    parent = path.parent
    return (
        parent.parent == CUSTOM_COVERS_DIR
        and str(parent.name) in CUSTOM_COVERS_GROUP_DIRS
        and match_image(path)
    )

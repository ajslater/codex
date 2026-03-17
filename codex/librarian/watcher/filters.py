"""Filter files."""

import re
from pathlib import Path

from comicbox.box import Comicbox
from loguru import logger

from codex.models import CustomCover
from codex.settings import CUSTOM_COVERS_DIR, CUSTOM_COVERS_GROUP_DIRS

_IMAGE_REGEX = r"\.(jpe?g|webp|png|gif|bmp)"


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


COMIC_MATCHER: re.Pattern = _build_comic_matcher()
IMAGE_MATCHER: re.Pattern = re.compile(_IMAGE_REGEX, re.IGNORECASE)


def match_suffix(pattern: re.Pattern, path: Path) -> bool:
    """Match suffix with pettern."""
    return bool(path and path.suffix and pattern.match(path.suffix) is not None)


def match_folder_cover(path: Path) -> bool:
    """Match a folder cover image (e.g. cover.jpg next to comics)."""
    return path.stem == CustomCover.FOLDER_COVER_STEM and match_suffix(
        IMAGE_MATCHER, path
    )


def match_group_cover_image(path: Path) -> bool:
    """Match a custom group cover image in the custom-covers directory."""
    parent = path.parent
    return (
        parent.parent == CUSTOM_COVERS_DIR
        and str(parent.name) in CUSTOM_COVERS_GROUP_DIRS
        and match_suffix(IMAGE_MATCHER, path)
    )

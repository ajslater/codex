"""Filesystem watching constants."""

import re

from comicbox.box import Comicbox
from loguru import logger

# Poller
DIR_NOT_FOUND_TIMEOUT = 15 * 60
DOCKER_UNMOUNTED_FN = "DOCKER_UNMOUNTED_VOLUME"

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

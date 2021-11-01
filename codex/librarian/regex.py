"""Regex to match comics."""

import re


COMIC_REGEX = r"\.cb[rz]$"
COMIC_MATCHER = re.compile(COMIC_REGEX)

"""Whitenoise setup functions."""

import re

IMF_RE = re.compile(r"^.+[.-][0-9a-zA-Z_-]{8,12}\..+$")


def immutable_file_test(_path, url):
    """For django-vite."""
    # Match filename with 12 hex digits before the extension
    # e.g. app.db8f2edc0c8a.js
    return IMF_RE.match(url)

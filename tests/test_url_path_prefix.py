"""
URL path prefix normalization.

``server.url_path_prefix`` is handed verbatim to Granian's ASGI ``root_path``,
which Django strips from the request path with ``removeprefix``. A prefix
without a leading slash (e.g. ``"codex"``) never matches the ``/codex/...``
request path, so ServeStatic 500s and ``STATIC_URL`` / email links come out
malformed. :func:`normalize_url_path_prefix` guards against that by forcing the
``root_path`` convention: one leading slash, no trailing slash.
"""

from __future__ import annotations

import pytest

from codex.settings.config import normalize_url_path_prefix


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("", ""),
        ("/", ""),
        ("codex", "/codex"),
        ("/codex", "/codex"),
        ("/codex/", "/codex"),
        ("codex/", "/codex"),
        ("//codex//", "/codex"),
        ("codex/app", "/codex/app"),
        ("/codex/app/", "/codex/app"),
    ],
)
def test_normalize_url_path_prefix(raw: str, expected: str) -> None:
    """A non-empty prefix gets one leading slash and no trailing slash."""
    assert normalize_url_path_prefix(raw) == expected

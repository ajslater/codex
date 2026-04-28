"""Spectacular hooks."""

from typing import Final

ALLOW_PREFIXES: Final = ("/api", "/opds")


def allow_list(endpoints) -> list:
    """Allow only API endpoints."""
    return [
        endpoint for endpoint in endpoints if endpoint[0].startswith(ALLOW_PREFIXES)
    ]

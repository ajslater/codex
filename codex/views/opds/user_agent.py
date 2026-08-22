"""OPDS Get User Agent."""

from contextlib import suppress
from typing import Final

from rest_framework.request import Request

# Clients whose feature support diverges by build under one UA name, so
# the build number right after the slash gates features. Panels: iOS
# builds (952+) render facets, the macOS build (951) does not.
_BUILD_UA_NAMES: Final = frozenset({"Panels"})


def get_user_agent_name(request: Request) -> tuple[str, int | None]:
    """Parse User Agent name, and build number for clients that need it."""
    build = None
    name, _, rest = (request.headers.get("User-Agent") or "").partition("/")
    if name in _BUILD_UA_NAMES and rest:
        with suppress(ValueError):
            build = int(rest.split(maxsplit=1)[0])
    return name, build

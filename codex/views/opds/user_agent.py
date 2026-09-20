"""OPDS Get User Agent."""

from rest_framework.request import Request


def get_user_agent_name(request: Request) -> str:
    """
    Parse the client name out of the User-Agent header.

    The name is everything before the first slash, which is all codex
    needs. The build number that used to follow it gated OPDS facets for
    Panels, until real user agents showed macOS build 957 and iOS build
    956 — one apart, interleaved, and with nothing else in the header to
    separate the platforms. No floor, denylist or allowlist survives
    that, so nothing reads the build any more.
    """
    name, _, _rest = (request.headers.get("User-Agent") or "").partition("/")
    return name

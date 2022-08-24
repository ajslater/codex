"""Spectacular hooks."""

ALLOW_PREFIXES = ("/api", "/opds")


def allow_list(endpoints):
    """Allow only API endpoints."""
    drf_endpoints = []
    for endpoint in endpoints:
        path = endpoint[0]
        for prefix in ALLOW_PREFIXES:
            if path.startswith(prefix):
                drf_endpoints += [endpoint]
                break
    return drf_endpoints

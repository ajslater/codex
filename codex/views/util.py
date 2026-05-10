"""Utility classes by many views."""

from collections.abc import Mapping
from dataclasses import dataclass
from functools import wraps
from typing import override

from django.utils.cache import patch_cache_control


def cache_control_2xx(**kwargs):
    """
    Patch ``Cache-Control`` only on 2xx responses.

    Like ``django.views.decorators.cache.cache_control`` but only
    emits the header for success responses.

    Django's ``cache_control`` patches the header onto every response,
    including 4xx and 5xx. With ``public, max-age=<long>`` that turns
    a transient error (a missing file, an ACL miss, a one-off
    backend hiccup) into a week-long cache poison: every browser that
    saw the failure keeps serving it from cache without ever reaching
    the server. This wrapper only marks success responses cacheable;
    errors are returned with whatever default headers DRF / Django
    already set (typically uncached).
    """

    def _wrap(viewfunc):
        @wraps(viewfunc)
        def _wrapped(request, *args, **kw):
            response = viewfunc(request, *args, **kw)
            status = getattr(response, "status_code", 0)
            if 200 <= status < 300:  # noqa: PLR2004
                patch_cache_control(response, **kwargs)
            return response

        return _wrapped

    return _wrap


@dataclass
class Route:
    """Breadcrumb, like a route."""

    group: str
    pks: tuple[int, ...]
    page: int = 1
    name: str = ""

    @override
    def __hash__(self) -> int:
        """Breadcrumb hash."""
        pk_parts = tuple(sorted(set(self.pks)))
        parts = (self.group, pk_parts, self.page)
        return hash(parts)

    @override
    def __eq__(self, cmp) -> bool:
        """Breadcrumb equality."""
        return cmp and hash(self) == hash(cmp)


def pop_name(kwargs: Mapping) -> Mapping:
    """Pop name from a mapping route."""
    kwargs = dict(kwargs)
    kwargs.pop("name", None)
    return kwargs

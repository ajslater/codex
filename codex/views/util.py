"""Utility classes by many views."""

import json
from collections.abc import Mapping
from contextlib import suppress
from dataclasses import dataclass
from json.decoder import JSONDecodeError
from typing import Any
from urllib.parse import unquote_plus

from djangorestframework_camel_case.settings import api_settings
from djangorestframework_camel_case.util import underscoreize

# Maximum cover size is around 24 Kb
DEFAULT_CHUNK_SIZE = 64 * 1024  # 64 Kb


@dataclass
class Route:
    """Breadcrumb, like a route."""

    group: str
    pks: tuple[int, ...]
    page: int = 1
    name: str = ""

    def __hash__(self):
        """Breadcrumb hash."""
        pk_parts = tuple(sorted(set(self.pks)))
        parts = (self.group, pk_parts, self.page)
        return hash(parts)

    def __eq__(self, cmp):
        """Breadcrumb equality."""
        return cmp and hash(self) == hash(cmp)

    def __and__(self, cmp):
        """Breadcrumb intersection."""
        return (
            bool(cmp is not None)
            and (self.group == cmp.group)
            and (self.pks == cmp.pks or (set(self.pks) & set(cmp.pks)))
        )


def reparse_json_query_params(query_params, keys) -> dict[str, Any]:
    """Reparse JSON encoded query_params."""
    # It is an unbelievable amount of trouble to try to parse axios native bracket
    # encoded complex objects in python
    parsed_dict = {}
    for key, value in query_params.items():
        if key in keys:
            parsed_value = unquote_plus(value)
            with suppress(JSONDecodeError):
                parsed_value = json.loads(parsed_value)
        else:
            parsed_value = value

        parsed_dict[key] = parsed_value
    return dict(underscoreize(parsed_dict, **api_settings.JSON_UNDERSCOREIZE))  # type:ignore[reportReturnType]


def pop_name(kwargs: Mapping):
    """Pop name from a mapping route."""
    kwargs = dict(kwargs)
    kwargs.pop("name", None)
    return kwargs


def chunker(open_file, chunk_size=DEFAULT_CHUNK_SIZE):
    """Asynchronous iterator for serving files."""
    with open_file:
        while True:
            if chunk := open_file.read(chunk_size):
                yield chunk
            else:
                break

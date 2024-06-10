"""Utility classes by many views."""

import json
from collections.abc import Mapping
from contextlib import suppress
from dataclasses import asdict, dataclass
from json.decoder import JSONDecodeError
from urllib.parse import unquote_plus

from djangorestframework_camel_case.settings import api_settings
from djangorestframework_camel_case.util import underscoreize


@dataclass()
class Route(dict):
    """Breadcrumb, like a route."""

    group: str
    pks: tuple[int, ...]
    page: int = 1
    name: str = ""

    def __eq__(self, cmp):
        """Breadcrumb equality."""
        return (
            bool(cmp is not None)
            and (self.group == cmp.group)
            and (set(self.pks) == set(cmp.pks))
            and (self.page == cmp.page)
        )

    def __and__(self, cmp):
        """Breadcrumb intersection."""
        return (
            bool(cmp is not None)
            and (self.group == cmp.group)
            and (self.pks == cmp.pks or (set(self.pks) & set(cmp.pks)))
        )

    dict = asdict


def reparse_json_query_params(query_params, keys) -> dict:
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
    return dict(underscoreize(parsed_dict, **api_settings.JSON_UNDERSCOREIZE))  # type:ignore


def pop_name(kwargs: Mapping):
    """Pop name from a mapping route."""
    kwargs = dict(kwargs)
    kwargs.pop("name", None)
    return kwargs

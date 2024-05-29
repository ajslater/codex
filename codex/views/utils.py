"""Utility functions for views."""

import json
from contextlib import suppress
from json.decoder import JSONDecodeError
from urllib.parse import unquote_plus

from djangorestframework_camel_case.settings import api_settings
from djangorestframework_camel_case.util import underscoreize


def reparse_json_query_params(query_params):
    """Reparse JSON encoded query_params."""
    # It is an unbelievable amount of trouble to try to parse axios native bracket
    # encoded complex objects in python
    parsed_dict = {}
    for key, value in query_params.items():
        parsed_value = unquote_plus(value)
        with suppress(JSONDecodeError):
            parsed_value = json.loads(parsed_value)

        parsed_dict[key] = parsed_value
    return underscoreize(parsed_dict, **api_settings.JSON_UNDERSCOREIZE)  # type:ignore

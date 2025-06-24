"""Serializer mixins."""

import json
from contextlib import suppress
from json.decoder import JSONDecodeError
from typing import Any
from urllib.parse import unquote_plus

from djangorestframework_camel_case.settings import api_settings
from djangorestframework_camel_case.util import underscoreize
from rest_framework.serializers import (
    BooleanField,
    Serializer,
)
from typing_extensions import override


class OKSerializer(Serializer):
    """Default serializer for views without much response."""

    ok = BooleanField(default=True)


class JSONFieldSerializer(Serializer):
    """Reparse JSON encoded query_params."""

    JSON_FIELDS: frozenset[str] = frozenset()

    @override
    def to_internal_value(self, data):
        """Reparse JSON encoded query_params."""
        # It is an unbelievable amount of trouble to try to parse axios native bracket
        # encoded complex objects in python
        parsed_dict: dict[str, Any] = {}
        for key, value in data.items():
            if key in self.JSON_FIELDS:
                parsed_value = unquote_plus(value)
                with suppress(JSONDecodeError):
                    parsed_value = json.loads(parsed_value)
            else:
                parsed_value = value

            parsed_dict[key] = parsed_value
        data = dict(underscoreize(parsed_dict, **api_settings.JSON_UNDERSCOREIZE))  # pyright: ignore[reportArgumentType,reportCallIssue]
        return super().to_internal_value(data)

"""Custom fields."""

from abc import ABC

import pycountry
from loguru import logger
from pycountry.db import Database
from rest_framework.serializers import (
    ChoiceField,
    ListField,
)
from typing_extensions import override

from codex.choices.browser import (
    BROWSER_BOOKMARK_FILTER_CHOICES,
    BROWSER_TOP_GROUP_CHOICES,
    DUMMY_NULL_NAME,
)
from codex.serializers.fields.sanitized import SanitizedCharField
from codex.serializers.route import RouteSerializer


class TopGroupField(ChoiceField):
    """Valid Top Groups Only."""

    class_choices = tuple(BROWSER_TOP_GROUP_CHOICES.keys())

    def __init__(self, *args, **kwargs):
        """Initialize with choices."""
        super().__init__(*args, choices=self.class_choices, **kwargs)


class BookmarkFilterField(ChoiceField):
    """Bookmark Choice Field."""

    def __init__(self, *args, **kwargs):
        """Use bookmark filter choices."""
        super().__init__(
            *args, choices=tuple(BROWSER_BOOKMARK_FILTER_CHOICES.keys()), **kwargs
        )


class PyCountryField(SanitizedCharField, ABC):
    """Serialize to a long pycountry name."""

    DB: Database = pycountry.countries
    _ALPHA_2_LEN = 2

    @override
    def to_representation(self, value):
        """Lookup the name with pycountry, just copy the value on fail."""
        if not value:
            return ""
        if value == DUMMY_NULL_NAME:
            return value
        try:
            # fix for https://github.com/flyingcircusio/pycountry/issues/41
            lookup_obj = (
                self.DB.get(alpha_2=value)
                if len(value) == self._ALPHA_2_LEN
                else self.DB.lookup(value)
            )
            # If lookup fails, return the key as the name
        except Exception:
            logger.warning(f"Could not serialize name with pycountry {value}")
            return value
        else:
            return lookup_obj.name if lookup_obj else value


class CountryField(PyCountryField):
    """Serializer to long country name."""

    DB: Database = pycountry.countries


class LanguageField(PyCountryField):
    """Serializer to long language name."""

    DB: Database = pycountry.languages


class BreadcrumbsField(ListField):
    """An Array of Routes."""

    child = RouteSerializer()  # pyright: ignore[reportIncompatibleUnannotatedOverride]

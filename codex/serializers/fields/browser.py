"""Custom fields."""

from abc import ABC
from typing import ClassVar, override

import pycountry
from loguru import logger
from pycountry.db import Database
from rest_framework.fields import CharField
from rest_framework.serializers import ListField

from codex.choices.browser import (
    BROWSER_BOOKMARK_FILTER_CHOICES,
    DUMMY_NULL_NAME,
)
from codex.serializers.fields.base import CodexChoiceField
from codex.serializers.route import RouteSerializer


class BookmarkFilterField(CodexChoiceField):
    """Bookmark Choice Field."""

    class_choices = tuple(BROWSER_BOOKMARK_FILTER_CHOICES.keys())


class PyCountryField(CharField, ABC):
    """
    Serialize to a long pycountry name.

    The hot path is alpha_2 input — a tiny ISO code (``"US"``,
    ``"FR"``, ``"EN"``) that pycountry resolves into a long display
    name. Build a ``{alpha_2: name}`` dict once per subclass on
    first use and serve the lookup from memory; that drops a per-
    field per-comic ``DB.get(alpha_2=...)`` round trip (~µs each)
    to a single dict ``get`` (~ns).

    pycountry data ships with the package and is immutable across
    the process lifetime. A server restart picks up package
    upgrades; in-process invalidation is unnecessary.

    Inherits from plain ``CharField`` rather than
    ``SanitizedCharField`` — ISO codes are alphanumeric by
    definition, so nh3 HTML sanitization on every write is dead
    work. Outer whitespace is stripped in
    :class:`codex.models.fields.CleaningStringFieldMixin` before
    a value ever reaches this field.
    """

    DB: Database = pycountry.countries
    _ALPHA_2_LEN = 2
    _alpha_2_map: ClassVar[dict[str, str] | None] = None

    @classmethod
    def _get_alpha_2_map(cls) -> dict[str, str]:
        """Lazy-build the alpha_2 → name projection on first call."""
        if cls._alpha_2_map is None:
            cls._alpha_2_map = {
                row.alpha_2: row.name for row in cls.DB if hasattr(row, "alpha_2")
            }
        return cls._alpha_2_map

    @override
    def to_representation(self, value) -> str:
        """Look up the long name via the cached alpha_2 map."""
        if not value:
            return ""
        if value == DUMMY_NULL_NAME:
            return value
        # Defensive ``.strip()``: belt-and-braces for the pycountry
        # cache lookup even if a row predates migration 0041.
        value = value.strip()
        if len(value) == self._ALPHA_2_LEN:
            return self._get_alpha_2_map().get(value, value)
        # Non-alpha_2 fallback — rare, e.g. legacy ``"eng"`` (alpha_3)
        # or a free-form name. Fuzzy ``DB.lookup`` covers both.
        try:
            row = self.DB.lookup(value)
        except (LookupError, KeyError):
            logger.warning(f"Could not serialize name with pycountry {value}")
            return value
        return row.name if row else value


class CountryField(PyCountryField):
    """Serializer to long country name."""

    DB: Database = pycountry.countries
    _alpha_2_map: ClassVar[dict[str, str] | None] = None


class LanguageField(PyCountryField):
    """Serializer to long language name."""

    DB: Database = pycountry.languages
    _alpha_2_map: ClassVar[dict[str, str] | None] = None


class BreadcrumbsField(ListField):
    """An Array of Routes."""

    child = RouteSerializer()

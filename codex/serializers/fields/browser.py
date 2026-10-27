"""Custom fields."""

import re
from abc import ABC
from functools import cache
from typing import ClassVar, Final, override

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

# MetronInfo v1.2's languageCode pattern: a BCP 47 tag.
_BCP47_RE: Final = re.compile(r"[a-zA-Z]{2,3}(-[a-zA-Z0-9]{1,8})*")


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

    @classmethod
    def _split(cls, value: str) -> tuple[str, str]:
        """Split a value into the code pycountry resolves and a suffix to keep."""
        return value, ""

    @classmethod
    def _lookup_name(cls, code: str) -> str | None:
        """Return the long name for one code, or None."""
        if len(code) == cls._ALPHA_2_LEN:
            return cls._get_alpha_2_map().get(code)
        # Non-alpha_2 fallback — rare, e.g. legacy ``"eng"`` (alpha_3)
        # or a free-form name. Fuzzy ``DB.lookup`` covers both.
        try:
            row = cls.DB.lookup(code)
        except (LookupError, KeyError):
            return None
        return row.name if row else None

    @classmethod
    @cache
    def display_name(cls, value: str) -> str:
        """
        Return the long name, or the value itself if pycountry can't name it.

        Cached per value, so an unknown value warns once rather than on
        every row that carries it.
        """
        # Defensive ``.strip()``: belt-and-braces for the pycountry
        # cache lookup even if a row predates migration 0041.
        value = value.strip()
        code, suffix = cls._split(value)
        name = cls._lookup_name(code)
        if name is None:
            logger.warning(f"Could not serialize name with pycountry {value}")
            return value
        return f"{name} ({suffix})" if suffix else name

    @override
    def to_representation(self, value) -> str:
        """Look up the long name via the cached alpha_2 map."""
        if not value:
            return ""
        if value == DUMMY_NULL_NAME:
            return value
        return self.display_name(value)


class CountryField(PyCountryField):
    """Serializer to long country name."""

    DB: Database = pycountry.countries
    _alpha_2_map: ClassVar[dict[str, str] | None] = None


class LanguageField(PyCountryField):
    """
    Serializer to long language name.

    Holds a BCP 47 tag: ``pt-BR`` reads ``Portuguese (BR)``, naming the
    primary language and keeping the script, region and variant subtags
    as given.
    """

    DB: Database = pycountry.languages
    _alpha_2_map: ClassVar[dict[str, str] | None] = None

    @override
    @classmethod
    def _split(cls, value: str) -> tuple[str, str]:
        """Split a BCP 47 tag into its primary language and the rest."""
        if not _BCP47_RE.fullmatch(value):
            # Not a tag: a language name like "English".
            return value, ""
        code, _, suffix = value.partition("-")
        # Primary language subtags are case-insensitive; pycountry's are lower.
        return code.lower(), suffix


class BreadcrumbsField(ListField):
    """An Array of Routes."""

    child = RouteSerializer()

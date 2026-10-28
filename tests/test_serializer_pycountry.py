"""Language and country codes serialize to names; BCP 47 tags keep their subtags."""

from collections.abc import Generator
from contextlib import contextmanager
from typing import Final

import pytest
from loguru import logger

from codex.serializers.browser.page import _apply_transform
from codex.serializers.fields.browser import CountryField, LanguageField

_UNKNOWN_TAG: Final = "xx-YY"


@contextmanager
def _capture_warnings() -> Generator[list[str]]:
    """Collect loguru WARNING+ messages emitted inside the ``with`` block."""
    records: list[str] = []
    sink_id = logger.add(records.append, level="WARNING", format="{message}")
    try:
        yield records
    finally:
        logger.remove(sink_id)


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        ("en", "English"),
        ("EN", "English"),
        ("fil", "Filipino"),
        ("pt-BR", "Portuguese (BR)"),
        ("zh-Hant", "Chinese (Hant)"),
        ("zh-Hant-TW", "Chinese (Hant-TW)"),
    ],
)
def test_language_tag_names(value: str, expected: str) -> None:
    """A tag reads as its language's name, with any other subtags after it."""
    assert LanguageField().to_representation(value) == expected
    # The browser table's language column reads the same name.
    assert _apply_transform("language", value) == expected


def test_country_names_are_not_split() -> None:
    """Only languages are tags; a hyphenated country name is left whole."""
    assert CountryField().to_representation("US") == "United States"
    assert CountryField().to_representation("Timor-Leste") == "Timor-Leste"


def test_an_unknown_tag_stays_raw_and_warns_once() -> None:
    """An unresolvable tag shows as itself and warns once, not once per row."""
    LanguageField.display_name.cache_clear()
    field = LanguageField()
    with _capture_warnings() as warnings:
        assert field.to_representation(_UNKNOWN_TAG) == _UNKNOWN_TAG
        assert field.to_representation(_UNKNOWN_TAG) == _UNKNOWN_TAG
        assert _apply_transform("language", _UNKNOWN_TAG) == _UNKNOWN_TAG
    assert [message for message in warnings if _UNKNOWN_TAG in message] == [
        f"Could not serialize name with pycountry {_UNKNOWN_TAG}\n"
    ]

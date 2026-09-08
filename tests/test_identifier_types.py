"""
The two identifier-type vocabularies must stay in step.

Codex names an identifier's type after the table it points at, comicbox
after the thing itself, and the bridge between them is derived from the
``IdentifierType`` member names rather than hand-written. These tests are
what makes that derivation safe: a type added to either side without a
matching member on the other fails here instead of silently importing
every affected id as an issue.
"""

from comicbox.identifiers import DEFAULT_ID_TYPE, ID_TYPE_NAMES

from codex.models.identifier import (
    COMICBOX_ID_TYPE_MAP,
    IdentifierType,
    to_codex_id_type,
    to_comicbox_id_type,
)


def test_every_codex_type_has_a_comicbox_name() -> None:
    """The map is total over codex's own vocabulary."""
    assert set(COMICBOX_ID_TYPE_MAP) == set(IdentifierType.values)


def test_every_comicbox_type_codex_names_is_real() -> None:
    """Codex never invents a type name comicbox would not recognize."""
    assert set(COMICBOX_ID_TYPE_MAP.values()) <= set(ID_TYPE_NAMES)


def test_comicbox_types_codex_cannot_express_are_known() -> None:
    """
    Whatever codex has no table for is listed here deliberately.

    An identifier of one of these types still imports; it is filed under
    the default type. This test exists so adding a table for one of them
    is a visible decision rather than a silent nonevent.
    """
    unexpressed = set(ID_TYPE_NAMES) - set(COMICBOX_ID_TYPE_MAP.values())
    assert unexpressed == set()


def test_absent_type_means_the_default() -> None:
    """An identifier states a type only when it isn't the implied one."""
    assert to_codex_id_type(None) == IdentifierType.ISSUE.value
    assert to_codex_id_type("") == IdentifierType.ISSUE.value
    assert to_comicbox_id_type(IdentifierType.ISSUE.value) == DEFAULT_ID_TYPE


def test_the_names_that_differ_translate_both_ways() -> None:
    """The four names the two vocabularies spell differently."""
    pairs = (
        ("arc", IdentifierType.ARC),
        ("issue", IdentifierType.ISSUE),
        ("creator", IdentifierType.CREATOR),
        ("role", IdentifierType.ROLE),
    )
    for comicbox_name, codex_type in pairs:
        assert to_codex_id_type(comicbox_name) == codex_type.value
        assert to_comicbox_id_type(codex_type.value) == comicbox_name


def test_a_stated_type_is_matched_whatever_its_case() -> None:
    """Hand-written metadata is not required to match comicbox's casing."""
    assert to_codex_id_type("ARC") == IdentifierType.ARC.value
    assert to_codex_id_type("Series") == IdentifierType.SERIES.value


def test_an_unknown_type_falls_back_rather_than_failing() -> None:
    """A type from a future comicbox imports as an issue, not an error."""
    assert to_codex_id_type("sasquatch") == IdentifierType.ISSUE.value
    assert to_comicbox_id_type("sasquatch") == DEFAULT_ID_TYPE

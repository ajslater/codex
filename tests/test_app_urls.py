"""Resolution tests for the main app SPA URL patterns."""

from typing import Final

from django.urls import resolve

_PK: Final = 42
_PARENT_IDS: Final = (5, 7)


def test_collection_root_serves_spa():
    """``/publishers`` resolves to the collection-root SPA pattern."""
    match = resolve("/publishers")
    assert match.url_name == "browser_root"
    assert match.kwargs["collection"] == "publishers"


def test_collection_parented_serves_spa():
    """``/series/5,7`` resolves with collection + parent ids."""
    match = resolve("/series/5,7")
    assert match.url_name == "browser"
    assert match.kwargs["collection"] == "series"
    assert match.kwargs["parent_ids"] == _PARENT_IDS


def test_reader_serves_spa():
    """``/read/42`` resolves to the reader (page is a ?page= query param)."""
    match = resolve(f"/read/{_PK}")
    assert match.url_name == "reader"
    assert match.kwargs["pk"] == _PK


def test_reader_pdf_downloads_file():
    """``/read/42/book.pdf`` resolves to the PDF download route."""
    assert resolve(f"/read/{_PK}/book.pdf").url_name == "reader_pdf"


def test_legacy_char_route_is_gone():
    """The legacy ``/p/0/1`` char route was removed — it falls to the catchall."""
    assert resolve("/p/0/1").url_name == "catchall"

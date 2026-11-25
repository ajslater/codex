"""
The positions a list page owns, for placing its missing issues.

A list with no comic to place them among has every missing issue on page 1
and no other page: what Django's paginator gives an empty list, which
allows an empty first page and refuses the rest.
"""

from django.test import SimpleTestCase

from codex.views.browser.missing_entries import PageBounds, page_bounds


class PageBoundsTests(SimpleTestCase):
    """Where each page of a list starts and stops."""

    def test_no_comic_puts_everything_on_page_one(self) -> None:
        assert page_bounds([], 1, 2, 0) == PageBounds()
        assert page_bounds([], 2, 2, 0) is None

    def test_pages_split_at_their_last_comic(self) -> None:
        positions = [1, 3, 5, 7, 9]
        assert page_bounds(positions, 1, 2, 0) == PageBounds(after=None, through=3)
        assert page_bounds(positions, 2, 2, 0) == PageBounds(after=3, through=7)
        assert page_bounds(positions, 3, 2, 0) == PageBounds(after=7, through=None)
        assert page_bounds(positions, 4, 2, 0) is None

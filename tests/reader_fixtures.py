"""A reader, a comic they can see, and one behind a group they are not in."""

import shutil
from pathlib import Path
from typing import ClassVar, Final, override

from django.contrib.auth.models import Group, User
from django.core.cache import cache
from django.test import Client, TestCase

from codex.models import Comic, Imprint, Library, Publisher, Series, Volume
from codex.models.auth import GroupAuth
from codex.startup import init_admin_flags

PASSWORD: Final = "reader-test-pw"  # noqa: S105


class ReaderFixture(TestCase):
    """
    A reader, a comic they can see, and one behind a group they are not in.

    Subclasses set ``TMP_DIR`` to a directory of their own, so suites that
    run side by side never ``rmtree`` each other's comics, and
    ``COMIC_PAGE_COUNT`` to the page count their tests assume.
    """

    TMP_DIR: ClassVar[Path]
    COMIC_PAGE_COUNT: ClassVar[int]

    @override
    def setUp(self) -> None:
        cache.clear()
        init_admin_flags()
        publisher = Publisher.objects.create(name="Pub")
        imprint = Imprint.objects.create(name="Imp", publisher=publisher)
        series = Series.objects.create(name="Ser", imprint=imprint, publisher=publisher)
        self.groups = (  # pyright: ignore[reportUninitializedInstanceVariable]
            publisher,
            imprint,
            series,
            Volume.objects.create(
                name="2024", series=series, imprint=imprint, publisher=publisher
            ),
        )
        self.library = self._make_library("open")  # pyright: ignore[reportUninitializedInstanceVariable]
        self.comic = self._make_comic(self.library, "open")  # pyright: ignore[reportUninitializedInstanceVariable]
        private_library = self._make_library("private")
        readers = Group.objects.create(name="readers")
        GroupAuth.objects.create(group=readers)
        private_library.groups.add(readers)
        self.private_comic = self._make_comic(private_library, "private")  # pyright: ignore[reportUninitializedInstanceVariable]
        self.user = User.objects.create_user(  # pyright: ignore[reportUninitializedInstanceVariable]
            username="reader", password=PASSWORD
        )
        self.client = Client()

    @override
    def tearDown(self) -> None:
        shutil.rmtree(self.TMP_DIR, ignore_errors=True)

    def _make_library(self, name: str) -> Library:
        path = self.TMP_DIR / name
        path.mkdir(exist_ok=True, parents=True)
        return Library.objects.create(path=str(path))

    def _make_comic(self, library: Library, name: str, **kwargs) -> Comic:
        path = Path(library.path) / f"{name}.cbz"
        path.write_bytes(name.encode() * 300)
        publisher, imprint, series, volume = self.groups
        return Comic.objects.create(
            library=library,
            path=path,
            issue_number=1,
            name=name,
            publisher=publisher,
            imprint=imprint,
            series=series,
            volume=volume,
            page_count=self.COMIC_PAGE_COUNT,
            size=42,
            **kwargs,
        )

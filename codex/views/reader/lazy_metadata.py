"""Lazily add metadata to books when loaded into the reader."""

from types import MappingProxyType

from comicbox.box import Comicbox
from loguru import logger

from codex.librarian.mp_queue import LIBRARIAN_QUEUE
from codex.librarian.scribe.tasks import LazyImportComicsTask
from codex.models import Comic
from codex.settings import COMICBOX_CONFIG
from codex.views.reader.arcs import ReaderArcsView

_LAZY_METADATA_ARGS = MappingProxyType({"prev": False, "current": True, "next": False})


class ReaderLazyMetadataView(ReaderArcsView):
    """Lazily add metadata to books when loaded into the reader."""

    @staticmethod
    def _lazy_metadata_comic(
        comic: Comic, import_pks: set[int], *, get_file_type: bool
    ):
        if comic and not (comic.page_count and (not get_file_type or comic.file_type)):
            with Comicbox(comic.path, config=COMICBOX_CONFIG, logger=logger) as cb:
                if get_file_type:
                    comic.file_type = cb.get_file_type() or ""
                comic.page_count = cb.get_page_count()
            import_pks.add(comic.pk)

    @classmethod
    def lazy_metadata(cls, books):
        """Get reader metadata from comicbox if it's not in the db."""
        import_pks = set()

        for key, get_file_type in _LAZY_METADATA_ARGS.items():
            comic = books.get(key)
            cls._lazy_metadata_comic(comic, import_pks, get_file_type=get_file_type)

        if import_pks:
            task = LazyImportComicsTask(pks=frozenset(import_pks))
            LIBRARIAN_QUEUE.put(task)

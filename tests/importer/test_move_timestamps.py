"""
A comic that leaves a collection must re-stamp the collection it left.

Editing a comic's metadata can move it out of a collection: a publisher/imprint/
series/volume change (FK move) or a story-arc change (m2m unlink). The
destination is re-stamped automatically (a current comic points into it), but
the *source* used to be left untouched — so the browser's ``library.changed``
refresh gate, which probes the viewed collection's ``updated_at``, never fired
for the source view.

Each test pre-creates the DB comic so the file's metadata differs from it, then
imports the file (the same update path a manual/online edit triggers) and
asserts the source collection's ``updated_at`` advances even when it is now
empty.
"""

from threading import Event, Lock
from typing import override

from loguru import logger

from codex.librarian.mp_queue import LIBRARIAN_QUEUE
from codex.librarian.scribe.importer.importer import ComicImporter
from codex.librarian.scribe.importer.tasks import ImportTask
from codex.models import (
    Comic,
    Imprint,
    Library,
    Publisher,
    Series,
    StoryArc,
    StoryArcNumber,
    Volume,
)
from tests.importer.test_basic import PATH, BaseTestImporter

_FILE_PUBLISHER = "Youthful Adventure Stories"
_SOURCE_PUBLISHER = "Throwaway Source Pub"


def _run_full_import(importer) -> None:
    """Run every importer phase in order (apply() without pragmas/finish)."""
    importer.read()
    importer.query()
    importer.create_all_fks()
    importer.update_all_fks()
    importer.prepare_fk_link_instance_maps()
    importer.update_comics()
    importer.create_comics()
    importer.link()
    importer.fail_imports()
    importer.delete()
    importer.full_text_search()


class TestImporterMoveRestampsSource(BaseTestImporter):
    """A publisher change re-stamps the collection the comic left."""

    @override
    def setUp(self) -> None:
        super().setUp()
        # Pre-create the comic under a source publisher that differs from the
        # one the file declares, so the import moves it.
        library = Library.objects.get(pk=self.task.library_id)
        pub = Publisher.objects.create(name=_SOURCE_PUBLISHER)
        imp = Imprint.objects.create(name="Src Imprint", publisher=pub)
        ser = Series.objects.create(name="Src Series", imprint=imp, publisher=pub)
        vol = Volume.objects.create(name="1", series=ser, imprint=imp, publisher=pub)
        Comic.objects.create(
            library=library,
            path=PATH,
            issue_number=1,
            name="src",
            publisher=pub,
            imprint=imp,
            series=ser,
            volume=vol,
            size=1,
            page_count=1,
        )
        self.source_pub = pub

    def test_publisher_move_restamps_source(self) -> None:
        old_mtime = Publisher.objects.get(pk=self.source_pub.pk).updated_at

        task = ImportTask(
            library_id=self.task.library_id,
            files_modified=frozenset({PATH}),
            force_import_metadata=True,
            check_metadata_mtime=False,
        )
        importer = ComicImporter(task, logger, LIBRARIAN_QUEUE, Lock(), Event())
        _run_full_import(importer)

        # The comic actually moved to the file's publisher...
        comic = Comic.objects.get(path=PATH)
        assert comic.publisher is not None
        assert comic.publisher.name == _FILE_PUBLISHER
        # ...and the source publisher (now empty) was still re-stamped so the
        # browser's library.changed gate fires for whoever was viewing it.
        new_mtime = Publisher.objects.get(pk=self.source_pub.pk).updated_at
        assert new_mtime > old_mtime, (new_mtime, old_mtime)


class TestImporterStoryArcRestampsSource(BaseTestImporter):
    """Removing a comic from a story arc (m2m) re-stamps the source arc."""

    @override
    def setUp(self) -> None:
        super().setUp()
        # Pre-create the comic linked to a story arc the file does NOT declare
        # (the file's arcs are c/d/e/f), so importing it removes that arc.
        library = Library.objects.get(pk=self.task.library_id)
        pub = Publisher.objects.create(name="Arc Test Pub")
        imp = Imprint.objects.create(name="Arc Imprint", publisher=pub)
        ser = Series.objects.create(name="Arc Series", imprint=imp, publisher=pub)
        vol = Volume.objects.create(name="1", series=ser, imprint=imp, publisher=pub)
        comic = Comic.objects.create(
            library=library,
            path=PATH,
            issue_number=1,
            name="arc",
            publisher=pub,
            imprint=imp,
            series=ser,
            volume=vol,
            size=1,
            page_count=1,
        )
        arc = StoryArc.objects.create(name="Removed Arc")
        san = StoryArcNumber.objects.create(story_arc=arc, number=1)
        comic.story_arc_numbers.add(san)
        self.removed_arc = arc

    def test_storyarc_removal_restamps_source(self) -> None:
        old_mtime = StoryArc.objects.get(pk=self.removed_arc.pk).updated_at

        task = ImportTask(
            library_id=self.task.library_id,
            files_modified=frozenset({PATH}),
            force_import_metadata=True,
            check_metadata_mtime=False,
        )
        importer = ComicImporter(task, logger, LIBRARIAN_QUEUE, Lock(), Event())
        _run_full_import(importer)

        # The comic moved to the file's arcs; "Removed Arc" lost it...
        comic = Comic.objects.get(path=PATH)
        arc_names = set(
            comic.story_arc_numbers.values_list("story_arc__name", flat=True)
        )
        assert "Removed Arc" not in arc_names, arc_names
        # ...and the source arc was re-stamped (m2m source re-stamp).
        new_mtime = StoryArc.objects.get(pk=self.removed_arc.pk).updated_at
        assert new_mtime > old_mtime, (new_mtime, old_mtime)

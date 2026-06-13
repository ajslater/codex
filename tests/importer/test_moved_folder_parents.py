"""
Moving a folder under a not-yet-tracked parent must create real parent folders.

When the poller reports a folder move whose destination parent isn't yet a
``Folder`` row, the importer creates the intermediate parent layers before
moving. ``_get_move_create_folders_one_layer`` feeds those paths to
``bulk_folders_create``, which expects each entry to be a key tuple
(``MODEL_REL_MAP[Folder] == (("path",), ...)``). It used to hand over bare path
strings, so ``bulk_folders_create``'s inner loop iterated each string character
by character and tried to ``stat('K')`` etc., crashing the ScribeThread with
``FileNotFoundError: 'K'``.
"""

from typing import override

from codex.models import Folder, Library
from tests.importer.test_basic import TMP_DIR, BaseTestImporter


class TestImporterMovedFolderCreatesParents(BaseTestImporter):
    """A folder move under a missing parent creates the real parent folder."""

    @override
    def setUp(self) -> None:
        super().setUp()
        library = Library.objects.get(pk=self.task.library_id)
        self.src_dir = TMP_DIR / "MovedDir"
        self.new_parent = TMP_DIR / "NewParent"
        self.dest_dir = self.new_parent / "MovedDir"
        self.src_dir.mkdir(exist_ok=True)
        self.dest_dir.mkdir(parents=True, exist_ok=True)

        # The source folder is tracked in the DB; its destination parent is not.
        src_folder = Folder(
            library=library, path=str(self.src_dir), name=self.src_dir.name
        )
        src_folder.presave()
        src_folder.save()
        self.library = library

    def test_moved_folder_creates_intermediate_parents(self) -> None:
        self.task.dirs_moved = {str(self.src_dir): str(self.dest_dir)}

        count = self.importer.bulk_folders_moved()

        # The intermediate parent folder was created from its real path...
        new_parent_folder = Folder.objects.get(
            library=self.library, path=str(self.new_parent)
        )
        assert new_parent_folder.name == "NewParent"
        # ...and the folder actually moved under it.
        moved = Folder.objects.get(library=self.library, path=str(self.dest_dir))
        assert moved.parent_folder_id == new_parent_folder.pk
        # No bogus single-character folders leaked in from char-iterating paths.
        assert not Folder.objects.filter(library=self.library, path="N").exists()
        assert count

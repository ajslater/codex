"""Test that an update import leaves an unchanged protagonist linked."""

from copy import deepcopy

from codex.librarian.scribe.importer.const import LINK_FKS, QUERY_MODELS
from codex.models import Comic, ScanInfo
from tests.importer.test_basic import AGGREGATED, PATH
from tests.importer.test_update_none import BaseTestImporterUpdate

PROTAGONIST = "Captain Science"
NEW_SCAN_INFO = "Rescanned"


class TestImporterUpdateProtagonist(BaseTestImporterUpdate):
    """
    Regression: re-importing with another FK changed must not clear the protagonist.

    The query prune pops "protagonist" from LINK_FKS when it already
    matches the DB, so the link phase sees a non-empty link_fks dict
    without a protagonist key. It used to treat that as "no protagonist"
    and NULL main_character/main_team on every such update.
    """

    @staticmethod
    def _assert_protagonist_linked(comic):
        """Assert the protagonist stays linked: Captain Science, no main team."""
        assert comic.main_character
        assert comic.main_character.name == PROTAGONIST
        assert comic.main_team is None

    def test_update_fk_change_keeps_protagonist(self):
        comic = Comic.objects.get(path=PATH)
        self._assert_protagonist_linked(comic)

        # Same file metadata except a changed scan_info tag.
        metadata: dict = deepcopy(dict(AGGREGATED))
        metadata[QUERY_MODELS][ScanInfo] = {(NEW_SCAN_INFO,): set()}
        metadata[LINK_FKS][PATH]["scan_info"] = (NEW_SCAN_INFO,)
        self.importer.metadata = metadata

        self.importer.query()
        # The unchanged protagonist is pruned; the changed FK survives.
        link_fks = self.importer.metadata[LINK_FKS][PATH]
        assert "protagonist" not in link_fks
        assert link_fks["scan_info"] == (NEW_SCAN_INFO,)

        self.importer.create_all_fks()
        self.importer.update_all_fks()
        self.importer.prepare_fk_link_instance_maps()
        self.importer.update_comics()
        self.importer.create_comics()

        comic = Comic.objects.get(path=PATH)
        assert comic.scan_info
        assert comic.scan_info.name == NEW_SCAN_INFO
        self._assert_protagonist_linked(comic)

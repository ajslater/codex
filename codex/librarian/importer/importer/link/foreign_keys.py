"""Bulk update m2m fields foreign keys."""

from contextlib import suppress
from pathlib import Path
from typing import TYPE_CHECKING

from comicbox.schemas.comicbox import PROTAGONIST_KEY

from codex.librarian.importer.importer.const import (
    LINK_FKS,
    PARENT_FOLDER_FIELD_NAME,
    PROTAGONIST_FIELD_MODEL_MAP,
)
from codex.librarian.importer.importer.link.const import (
    DEFAULT_KEY_RELS,
    GROUP_KEY_RELS,
)
from codex.librarian.importer.importer.link.covers import LinkCoversImporter
from codex.models import Folder
from codex.models.comic import Comic

if TYPE_CHECKING:
    from codex.models.base import BaseModel


class LinkComicForeignKeysImporter(LinkCoversImporter):
    """Link comics methods."""

    def _get_comic_folder_fk_link(self, md, path):
        parent_path = Path(path).parent
        md[PARENT_FOLDER_FIELD_NAME] = Folder.objects.get(path=parent_path)

    def _get_comic_protagonist_fk_link(self, md, path):
        """Protagonist does not create. Only links."""
        name = self.metadata[LINK_FKS][path].pop(PROTAGONIST_KEY, None)
        if not name:
            return
        name = name[0]
        for (
            protagonist_field_name,
            protagonist_model,
        ) in PROTAGONIST_FIELD_MODEL_MAP.items():
            with suppress(protagonist_model.DoesNotExist):
                md[protagonist_field_name] = protagonist_model.objects.get(name=name)
                break

    def _get_comic_simple_fk_links(self, md, path):
        link_fks = self.metadata[LINK_FKS].pop(path, {})
        for field_name, values in link_fks.items():
            model: type[BaseModel] = Comic._meta.get_field(field_name).related_model  # pyright: ignore[reportAssignmentType]
            key_rels = GROUP_KEY_RELS.get(model, DEFAULT_KEY_RELS)
            filter_dict = dict(zip(key_rels, values, strict=True))
            md[field_name] = model.objects.get(**filter_dict)

    def get_comic_fk_links(self, path):
        """Get links for all foreign keys for creating and updating."""
        md = {}
        self._get_comic_folder_fk_link(md, path)
        self._get_comic_protagonist_fk_link(md, path)
        self._get_comic_simple_fk_links(md, path)
        return md

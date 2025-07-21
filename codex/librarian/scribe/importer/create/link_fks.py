"""Bulk update m2m fields foreign keys."""

from contextlib import suppress
from pathlib import Path
from typing import TYPE_CHECKING

from comicbox.schemas.comicbox import PROTAGONIST_KEY

from codex.librarian.scribe.importer.const import (
    LINK_FKS,
    PARENT_FOLDER_FIELD_NAME,
    PROTAGONIST_FIELD_MODEL_MAP,
    VOLUME_FIELD_NAME,
)
from codex.librarian.scribe.importer.link import LinkComicsImporter
from codex.librarian.scribe.importer.link.const import (
    DEFAULT_KEY_RELS,
    GROUP_KEY_RELS,
)
from codex.models import Folder
from codex.models.comic import Comic

if TYPE_CHECKING:
    from codex.models.base import BaseModel


class CreateForeignKeyLinksImporter(LinkComicsImporter):
    """Link comics methods."""

    def _get_comic_folder_fk_link(self, md, subkey: int | str, path: str):
        parent_path = str(Path(path).parent)
        md[PARENT_FOLDER_FIELD_NAME] = Folder.objects.get(path=parent_path)
        self.add_links_to_fts(
            subkey,
            PARENT_FOLDER_FIELD_NAME,
            (parent_path,),
        )

    def _get_comic_protagonist_fk_link(self, md, link_fks: dict[str, tuple]):
        """Protagonist does not create. Only links."""
        if name := link_fks.pop(PROTAGONIST_KEY, None):
            name = name[0]
        for field_name, protagonist_model in PROTAGONIST_FIELD_MODEL_MAP.items():
            value = None
            if name:
                with suppress(protagonist_model.DoesNotExist):
                    value = protagonist_model.objects.get(name=name)
            md[field_name] = value

    def _get_comic_simple_fk_links(
        self, md, subkey: int | str, link_fks: dict[str, tuple]
    ):
        for field_name in tuple(link_fks.keys()):
            model: type[BaseModel] = Comic._meta.get_field(field_name).related_model  # pyright: ignore[reportAssignmentType], # ty: ignore[invalid-assignment]│
            key_rels = GROUP_KEY_RELS.get(model, DEFAULT_KEY_RELS)
            values = link_fks.pop(field_name)
            filter_dict = dict(zip(key_rels, values, strict=True))
            md[field_name] = model.objects.get(**filter_dict)
            if field_name != VOLUME_FIELD_NAME:
                self.add_links_to_fts(
                    subkey,
                    field_name,
                    (values[-1],),
                )

    def get_comic_fk_links(self, subkey: str | int, path: str):
        """Get links for all foreign keys for creating and updating."""
        md = {}
        self._get_comic_folder_fk_link(md, subkey, path)
        if link_fks := self.metadata[LINK_FKS].pop(path, {}):
            self._get_comic_protagonist_fk_link(md, link_fks)
            self._get_comic_simple_fk_links(md, subkey, link_fks)
        return md

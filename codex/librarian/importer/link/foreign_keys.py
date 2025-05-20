"""Bulk update m2m fields foreign keys."""

from contextlib import suppress
from pathlib import Path

from comicbox.schemas.comicbox import PROTAGONIST_KEY

from codex.librarian.importer.const import (
    FK_LINK,
    IMPRINT,
    PARENT_FOLDER,
    PROTAGONIST_FIELD_MODEL_MAP,
    PUBLISHER,
    SERIES,
    VOLUME,
)
from codex.librarian.importer.link.const import COMIC_FK_FIELD_NAME_AND_MODEL
from codex.librarian.importer.link.covers import LinkCoversImporter
from codex.models import (
    Folder,
    Imprint,
    Publisher,
    Series,
    Volume,
)


class LinkComicForiegnKeysImporter(LinkCoversImporter):
    """Link comics methods."""

    def _get_group_name(self, path, group_class):
        """Get the name of the browse group."""
        field_name = group_class.__name__.lower()
        return self.metadata[FK_LINK][path].pop(field_name, group_class.DEFAULT_NAME)

    def _get_comic_group_fk_links(self, md, path):
        publisher_name = self._get_group_name(path, Publisher)
        imprint_name = self._get_group_name(path, Imprint)
        series_name = self._get_group_name(path, Series)
        volume_name = self._get_group_name(path, Volume)
        md[PUBLISHER] = Publisher.objects.get(name=publisher_name)
        md[IMPRINT] = Imprint.objects.get(
            publisher__name=publisher_name, name=imprint_name
        )
        md[SERIES] = Series.objects.get(
            publisher__name=publisher_name, imprint__name=imprint_name, name=series_name
        )
        md[VOLUME] = Volume.objects.get(
            publisher__name=publisher_name,
            imprint__name=imprint_name,
            series__name=series_name,
            name=volume_name,
        )

    def _get_comic_folder_fk_link(self, md, path):
        parent_path = Path(path).parent
        md[PARENT_FOLDER] = Folder.objects.get(path=parent_path)

    def _get_comic_protagonist_fk_link(self, md, path):
        """Protagonist does not create. Only links."""
        name = self.metadata[FK_LINK][path].pop(PROTAGONIST_KEY, None)
        if not name:
            return
        for (
            protagonist_field_name,
            protagonist_model,
        ) in PROTAGONIST_FIELD_MODEL_MAP.items():
            with suppress(protagonist_model.DoesNotExist):
                md[protagonist_field_name] = protagonist_model.objects.get(name=name)
                break

    def _get_comic_simple_fk_links(self, md, path):
        for field_name, fk_model in COMIC_FK_FIELD_NAME_AND_MODEL.items():
            if name := self.metadata[FK_LINK][path].pop(field_name, None):
                md[field_name] = fk_model.objects.get(name=name)
        self.metadata[FK_LINK].pop(path)

    def get_comic_fk_links(self, md, path):
        """Get links for all foreign keys for creating and updating."""
        self._get_comic_group_fk_links(md, path)
        self._get_comic_folder_fk_link(md, path)
        self._get_comic_protagonist_fk_link(md, path)
        self._get_comic_simple_fk_links(md, path)

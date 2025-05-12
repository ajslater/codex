"""Bulk update m2m fields foreign keys."""

from pathlib import Path

from codex.librarian.importer.const import (
    COMIC_FK_FIELD_NAME_AND_MODEL,
    FK_LINK,
    IMPRINT,
    PARENT_FOLDER,
    PUBLISHER,
    SERIES,
    VOLUME,
)
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

    def get_comic_fk_links(self, md, path):
        """Get links for all foreign keys for creating and updating."""
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
        parent_path = Path(path).parent
        md[PARENT_FOLDER] = Folder.objects.get(path=parent_path)
        for field_name, fk_model in COMIC_FK_FIELD_NAME_AND_MODEL.items():
            if name := self.metadata[FK_LINK][path].pop(field_name, None):
                md[field_name] = fk_model.objects.get(name=name)
        self.metadata[FK_LINK].pop(path)

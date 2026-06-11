"""Bulk update m2m fields foreign keys."""

from pathlib import Path
from typing import TYPE_CHECKING, cast

from comicbox.formats.comicbox.schema import PROTAGONIST_KEY

from codex.librarian.scribe.importer.const import (
    CREATE_COMICS,
    LINK_FKS,
    PARENT_FOLDER_FIELD_NAME,
    PROTAGONIST_FIELD_MODEL_MAP,
    VOLUME_FIELD_NAME,
)
from codex.librarian.scribe.importer.link import LinkComicsImporter
from codex.models import Folder
from codex.models.comic import Comic
from codex.settings import IMPORTER_LINK_FK_BATCH_SIZE

if TYPE_CHECKING:
    from codex.models.base import BaseModel


class CreateForeignKeyLinksImporter(LinkComicsImporter):
    """
    Link comics methods.

    FK links resolve through per-chunk instance maps built by
    ``prepare_fk_link_instance_maps`` — one batched query per referenced
    field over the distinct key tuples — instead of one ``objects.get``
    per (comic, field), which dominated comic creation. Instances (not
    pks) are mapped so downstream stays unchanged: ``Comic(**md)``,
    the update path's setattr/default handling, and ``presave``'s
    ``age_rating`` dereference all keep working without lazy loads.
    """

    def _build_fk_instance_map(
        self, field_name: str, key_tuples: set[tuple]
    ) -> dict[tuple, "BaseModel"]:
        """Resolve one field's distinct key tuples to model instances."""
        pk_map = self._build_field_pk_map(field_name, key_tuples)
        if not pk_map:
            return {}
        model = cast("type[BaseModel]", Comic._meta.get_field(field_name).related_model)
        instances: dict[int, BaseModel] = {}
        pks = tuple(pk_map.values())
        for start in range(0, len(pks), IMPORTER_LINK_FK_BATCH_SIZE):
            batch = pks[start : start + IMPORTER_LINK_FK_BATCH_SIZE]
            instances.update(model.objects.in_bulk(batch))
        return {key: instances[pk] for key, pk in pk_map.items() if pk in instances}

    def _build_protagonist_instance_maps(
        self, names: set[str]
    ) -> dict[str, dict[str, "BaseModel"]]:
        """Resolve protagonist names to Character/Team instances."""
        maps: dict[str, dict[str, BaseModel]] = {}
        name_list = tuple(sorted(names))
        for field_name, model in PROTAGONIST_FIELD_MODEL_MAP.items():
            field_map: dict[str, BaseModel] = {}
            for start in range(0, len(name_list), IMPORTER_LINK_FK_BATCH_SIZE):
                batch = name_list[start : start + IMPORTER_LINK_FK_BATCH_SIZE]
                for obj in model.objects.filter(name__in=batch):
                    field_map[obj.name] = obj
            maps[field_name] = field_map
        return maps

    def _build_parent_folder_map(self) -> dict[str, Folder]:
        """Resolve the distinct parent dirs of the comics to be created."""
        parent_paths = tuple(
            sorted({str(Path(path).parent) for path in self.metadata[CREATE_COMICS]})
        )
        folder_map: dict[str, Folder] = {}
        for start in range(0, len(parent_paths), IMPORTER_LINK_FK_BATCH_SIZE):
            batch = parent_paths[start : start + IMPORTER_LINK_FK_BATCH_SIZE]
            for folder in Folder.objects.filter(library=self.library, path__in=batch):
                folder_map[folder.path] = folder
        return folder_map

    def prepare_fk_link_instance_maps(self) -> None:
        """
        Batch-resolve every pending FK link for this chunk.

        Runs after the FK create/update steps so newly created rows
        (tags, folders, collections) are resolvable. Walks LINK_FKS
        once collecting distinct key tuples per field, then issues one
        batched query per referenced field.
        """
        per_field: dict[str, set[tuple]] = {}
        prot_names: set[str] = set()
        for link_fks in self.metadata.get(LINK_FKS, {}).values():
            for field_name, values in link_fks.items():
                if field_name == PROTAGONIST_KEY:
                    if values and values[0]:
                        prot_names.add(values[0])
                elif values:
                    per_field.setdefault(field_name, set()).add(values)
        self.fk_link_instance_maps = {
            field_name: self._build_fk_instance_map(field_name, key_tuples)
            for field_name, key_tuples in per_field.items()
        }
        self.protagonist_instance_maps = self._build_protagonist_instance_maps(
            prot_names
        )
        self.parent_folder_map = self._build_parent_folder_map()

    def clear_fk_link_instance_maps(self) -> None:
        """Free the per-chunk instance maps."""
        self.fk_link_instance_maps = {}
        self.protagonist_instance_maps = {}
        self.parent_folder_map = {}

    def _get_comic_folder_fk_link(self, md, subkey: int | str, path: str) -> None:
        parent_path = str(Path(path).parent)
        folder = self.parent_folder_map.get(parent_path)
        if folder is None:
            raise Folder.DoesNotExist(parent_path)
        md[PARENT_FOLDER_FIELD_NAME] = folder
        self.add_links_to_fts(
            subkey,
            PARENT_FOLDER_FIELD_NAME,
            (parent_path,),
        )

    def _get_comic_protagonist_fk_link(
        self, md, link_fks: dict[str, tuple], *, for_create: bool
    ) -> None:
        """Protagonist does not create. Only links."""
        if PROTAGONIST_KEY not in link_fks and not for_create:
            # Update path: an absent key means the query prune dropped an
            # unchanged protagonist (or the file never tagged one) — leave
            # the existing links alone instead of clearing them.
            return
        name_tuple = link_fks.pop(PROTAGONIST_KEY, None)
        name: str | None = name_tuple[0] if name_tuple else None
        for field_name in PROTAGONIST_FIELD_MODEL_MAP:
            value = (
                self.protagonist_instance_maps.get(field_name, {}).get(name)
                if name
                else None
            )
            md[field_name] = value
            if value is not None:
                # A name that is both a Character and a Team links only
                # the first field (main_character), never both.
                name = None

    def _get_comic_simple_fk_links(
        self, md, subkey: int | str, link_fks: dict[str, tuple]
    ) -> None:
        for field_name in tuple(link_fks.keys()):
            values = link_fks.pop(field_name)
            instance = self.fk_link_instance_maps.get(field_name, {}).get(values)
            if instance is None:
                model = cast(
                    "type[BaseModel]",
                    Comic._meta.get_field(field_name).related_model,
                )
                reason = f"{field_name} {values}"
                raise model.DoesNotExist(reason)
            md[field_name] = instance
            if field_name != VOLUME_FIELD_NAME:
                self.add_links_to_fts(
                    subkey,
                    field_name,
                    (values[-1],),
                )

    def get_comic_fk_links(
        self, subkey: str | int, path: str, *, for_create: bool
    ) -> dict:
        """
        Get links for all foreign keys for creating and updating.

        ``for_create=True`` resolves ``parent_folder`` from the
        comic's path string. ``for_create=False`` (the update path)
        skips that lookup entirely — the comic already carries a
        valid ``parent_folder_id`` from a prior import (or from
        ``MovedComicsImporter._prepare_moved_comic`` if the file
        was renamed in this run), and re-resolving by string is
        wasted work that's also brittle against any string-form
        drift between ``Folder.path`` and
        ``str(Path(comic.path).parent)``.
        """
        md = {}
        if for_create:
            self._get_comic_folder_fk_link(md, subkey, path)
        if link_fks := self.metadata[LINK_FKS].pop(path, {}):
            self._get_comic_protagonist_fk_link(md, link_fks, for_create=for_create)
            self._get_comic_simple_fk_links(md, subkey, link_fks)
        return md

"""Aggregate Browser Group Trees."""

from collections.abc import Mapping
from contextlib import suppress

from comicbox.identifiers import IdSources
from comicbox.schemas.comicbox import (
    ID_KEY_KEY,
    ID_URL_KEY,
    IDENTIFIERS_KEY,
    NAME_KEY,
    NUMBER_KEY,
    PROTAGONIST_KEY,
)
from django.db.models import Field
from django.db.models.base import Model

from codex.librarian.importer.aggregate.const import COMIC_FK_FIELD_NAMES_FIELD_MAP
from codex.librarian.importer.const import (
    GROUP_MODEL_COUNT_FIELDS,
    LINK_FKS,
    QUERY_MODELS,
    get_key_index,
)
from codex.librarian.importer.extract import ExtractMetadataImporter
from codex.models.base import BaseModel
from codex.models.groups import BrowserGroupModel, Volume
from codex.models.identifier import Identifier, IdentifierSource
from codex.util import max_none


class AggregateForeignKeyMetadataImporter(ExtractMetadataImporter):
    """Aggregate Browser Group Trees."""

    def add_query_model(self, model: type[Model], clean_values):
        """Add to the queury models set for the model."""
        if model not in self.metadata[QUERY_MODELS]:
            self.metadata[QUERY_MODELS][model] = set()
        if not isinstance(clean_values, set | frozenset):
            clean_values = {
                clean_values,
            }
        if "metron" in clean_values:
            raise ValueError
        self.metadata[QUERY_MODELS][model] |= clean_values

    def get_identifier_tuple(self, model: type[BaseModel], obj: Mapping):
        """Parse first highest priority identifier from metadata."""
        # Used by Objects with identifiers, not comic itself.
        identifiers = obj.get(IDENTIFIERS_KEY)
        if not identifiers:
            return None

        for id_source_enum in IdSources:
            id_source = id_source_enum.value
            if id_obj := identifiers.get(id_source):
                break
        else:
            id_source, id_obj = next(identifiers.items())

        if not id_obj:
            return None

        id_type = model._meta.db_table.removeprefix("codex_")

        id_key = id_obj.get(ID_KEY_KEY)
        if not id_key:
            return None
        id_url = id_obj.get(ID_URL_KEY)

        identifier_tuple = (id_source, id_type, id_key, id_url)
        self.add_query_model(IdentifierSource, (id_source,))
        self.add_query_model(Identifier, identifier_tuple)

        return identifier_tuple[:-1]

    def _set_simple_fk(self, related_field: Field, value) -> tuple:
        value = related_field.get_prep_value(value)
        if value is None:
            return ()
        return (value,)

    def _set_group_tree_group(
        self,
        model: type[BrowserGroupModel],
        name_field: Field,
        group: dict | None,
        group_list: list,
    ) -> tuple:
        name_key = NUMBER_KEY if model == Volume else NAME_KEY
        if group is None:
            group = {}

        group_name = group.get(name_key, model.DEFAULT_NAME)
        clean_group_name = name_field.get_prep_value(group_name)
        group_list.append(clean_group_name)
        extra_vals = []
        if model != Volume:
            identifier_tuple = self.get_identifier_tuple(model, group)
            extra_vals.append(identifier_tuple)
        count_key = GROUP_MODEL_COUNT_FIELDS[model]
        if count_key:
            count = group.get(count_key)
            with suppress(Exception):
                old_count_val = (
                    self.metadata[QUERY_MODELS].get(model, {}).get(group_list)
                )
                count = max_none(old_count_val, count)
            extra_vals.append(count)
        return tuple(group_list + extra_vals)

    def get_fk_metadata(self, md, path):
        """Aggregate Simple Foreign Keys."""
        group_list = []
        for field_name, related_field in COMIC_FK_FIELD_NAMES_FIELD_MAP.items():
            # No identifiers on many2one fks yet
            # md_key = FIELD_NAME_TO_MD_KEY_MAP.get(field_name, field_name) if they ever diverge
            model = related_field.model
            md_key = field_name
            value = md.pop(md_key, None)
            if value is None and not issubclass(model, BrowserGroupModel):
                continue

            if issubclass(model, BrowserGroupModel):
                values = self._set_group_tree_group(
                    model, related_field, value, group_list
                )
            else:
                values = self._set_simple_fk(related_field, value)
            if not values and not issubclass(model, BrowserGroupModel):
                continue

            if md_key != PROTAGONIST_KEY:
                self.add_query_model(model, values)
            key_index = get_key_index(model)
            key_values = values[:key_index]
            self.metadata[LINK_FKS][path][field_name] = key_values

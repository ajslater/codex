"""Aggregate Browser Group Trees."""

from collections.abc import Mapping
from contextlib import suppress

from comicbox.fields.number_fields import PAGE_COUNT_KEY
from comicbox.identifiers import IdSources
from comicbox.schemas.comicbox import (
    ID_KEY_KEY,
    ID_URL_KEY,
    IDENTIFIERS_KEY,
    NAME_KEY,
    NUMBER_KEY,
    NUMBER_TO_KEY,
    PROTAGONIST_KEY,
)
from django.db.models import Field
from django.db.models.base import Model

from codex.librarian.scribe.importer.const import (
    GROUP_FIELD_NAMES,
    GROUP_FIELD_NAMES_SET,
    GROUP_MODEL_COUNT_FIELDS,
    LINK_FKS,
    QUERY_MODELS,
)
from codex.librarian.scribe.importer.query import QueryForeignKeysImporter
from codex.librarian.scribe.importer.read.const import (
    COMIC_FK_FIELD_NAMES,
    COMIC_FK_FIELD_NAMES_FIELD_MAP,
)
from codex.models.base import BaseModel
from codex.models.groups import BrowserGroupModel, Volume
from codex.models.identifier import Identifier, IdentifierSource
from codex.util import max_none

_MINIMAL_KEYS = frozenset({"file_type", PAGE_COUNT_KEY, "path"} | GROUP_FIELD_NAMES_SET)


class AggregateForeignKeyMetadataImporter(QueryForeignKeysImporter):
    """Aggregate Browser Group Trees."""

    def add_query_model(
        self,
        model: type[Model],
        clean_key_values: tuple,
        clean_extra_values: frozenset | set | None = None,
    ):
        """Add to the queury models set for the model."""
        if model not in self.metadata[QUERY_MODELS]:
            self.metadata[QUERY_MODELS][model] = {}
        if clean_key_values not in self.metadata[QUERY_MODELS][model]:
            self.metadata[QUERY_MODELS][model][clean_key_values] = set()
        if clean_extra_values is None:
            clean_extra_values = frozenset()
        else:
            clean_extra_values = frozenset(clean_extra_values)
        self.metadata[QUERY_MODELS][model][clean_key_values] |= clean_extra_values

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

        identifier_tuple_keys = None
        if id_source:
            self.add_query_model(IdentifierSource, (id_source,))
        identifier_tuple_keys = (id_source, id_type, id_key)
        id_url = id_obj.get(ID_URL_KEY)
        identifier_tuple_extra = frozenset([(id_url,)])
        self.add_query_model(Identifier, identifier_tuple_keys, identifier_tuple_extra)

        return identifier_tuple_keys

    def _set_simple_fk(self, related_field: Field, value) -> tuple:
        value = related_field.get_prep_value(value)
        if value is None:
            return ()
        return (value,), None

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
        if model == Volume:
            number_to = group.get(NUMBER_TO_KEY, model.DEFAULT_NAME)
            clean_number_to = name_field.get_prep_value(number_to)
            group_list.append(clean_number_to)
        else:
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
        return tuple(group_list), frozenset((tuple(extra_vals),))

    def get_fk_metadata(self, md, path):
        """Aggregate Simple Foreign Keys."""
        group_list = []
        # prevents skipped metadata from destroying browser group links
        field_names = tuple(GROUP_FIELD_NAMES) + tuple(
            sorted((set(md.keys()) - _MINIMAL_KEYS) & COMIC_FK_FIELD_NAMES)
        )
        for field_name in field_names:
            related_field = COMIC_FK_FIELD_NAMES_FIELD_MAP[field_name]
            # No identifiers on many2one fks yet
            # md_key = FIELD_NAME_TO_MD_KEY_MAP.get(field_name, field_name) if they ever diverge
            model: type[BaseModel] = related_field.model  # pyright: ignore[reportAssignmentType], # ty: ignore[invalid-assignment]
            md_key = field_name
            value = md.pop(md_key, None)

            if issubclass(model, BrowserGroupModel):
                key_values, extra_values = self._set_group_tree_group(
                    model, related_field, value, group_list
                )
            elif value is None:
                continue
            else:
                key_values, extra_values = self._set_simple_fk(related_field, value)
            if not key_values and not extra_values:
                continue
            if md_key != PROTAGONIST_KEY:  # pyright: ignore[reportUnnecessaryComparison]
                self.add_query_model(model, key_values, extra_values)
            self.metadata[LINK_FKS][path][field_name] = key_values

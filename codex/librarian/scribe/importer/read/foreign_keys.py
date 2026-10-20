"""Aggregate Browser Collection Trees."""

from collections.abc import Mapping
from types import MappingProxyType

from comicbox.enums.comicbox import IdSources
from comicbox.formats.comicbox.schema import (
    IDENTIFIERS_KEY,
    NAME_KEY,
    NUMBER_KEY,
    PAGE_COUNT_KEY,
    PROTAGONIST_KEY,
    VOLUME_NUMBER_TO_KEY,
)
from comicbox.identifiers import ID_KEY_KEY, ID_TYPE_KEY
from comicbox.identifiers.identifiers import get_identifier_url
from django.db.models import Field
from django.db.models.base import Model

from codex.librarian.scribe.importer.const import (
    COLLECTION_FIELD_NAMES,
    COLLECTION_FIELD_NAMES_SET,
    COLLECTION_MODEL_ATTR_FIELDS,
    END_YEAR_FIELD_NAME,
    LINK_FKS,
    QUERY_MODELS,
    START_YEAR_FIELD_NAME,
    STATUS_FIELD_NAME,
    SUMMARY_FIELD_NAME,
)
from codex.librarian.scribe.importer.query import QueryForeignKeysImporter
from codex.librarian.scribe.importer.read.const import (
    COMIC_FK_FIELD_NAMES,
    COMIC_FK_FIELD_NAMES_FIELD_MAP,
)
from codex.models.base import BaseModel
from codex.models.collections import BrowserCollectionModel, Volume
from codex.models.identifier import (
    Identifier,
    IdentifierSource,
    positional_id_type,
    to_codex_id_type,
    to_comicbox_id_type,
)
from codex.util import first_none, max_none, min_none

_MINIMAL_KEYS = frozenset(
    {"file_type", PAGE_COUNT_KEY, "path"} | COLLECTION_FIELD_NAMES_SET
)
# How comics of one collection in an import batch combine an attribute.
# Counts and the end year take the largest, the start year the earliest
# and text the first comic's.
_ATTR_MERGE = MappingProxyType(
    {
        START_YEAR_FIELD_NAME: min_none,
        END_YEAR_FIELD_NAME: max_none,
        STATUS_FIELD_NAME: first_none,
        SUMMARY_FIELD_NAME: first_none,
    }
)


class AggregateForeignKeyMetadataImporter(QueryForeignKeysImporter):
    """Aggregate Browser Collection Trees."""

    def add_query_model(
        self,
        model: type[Model],
        clean_key_values: tuple,
        clean_extra_values: frozenset | set | None = None,
    ) -> None:
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

    @staticmethod
    def _identifier_url(id_source: str, id_type: str, id_obj: Mapping) -> str:
        """
        Derive the web link for one identifier.

        Comicbox identifiers carry no url of their own: a synthesized
        copy stored beside the key could disagree with it, so comicbox
        derives links from the key on demand and codex derives its own
        column the same way.

        An identifier states its type only when that type isn't the one
        its position implies, so a character's identifier with nothing
        stated is a character id. What a position implies is a question
        about the id, not about the row it hangs on, which is why this
        does not simply reuse the codex table name.
        """
        stated_type = id_obj.get(ID_TYPE_KEY)
        comicbox_id_type = (
            to_comicbox_id_type(to_codex_id_type(stated_type))
            if stated_type
            else positional_id_type(id_type)
        )
        return get_identifier_url(
            id_source, comicbox_id_type, id_obj.get(ID_KEY_KEY, "")
        )

    def get_identifier_tuple(
        self, model: type[BaseModel], obj: Mapping
    ) -> tuple | None:
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

        if id_source:
            self.add_query_model(IdentifierSource, (id_source,))
        identifier_tuple_keys = (id_source, id_type, id_key)
        id_url = self._identifier_url(id_source, id_type, id_obj)
        identifier_tuple_extra = frozenset([(id_url,)])
        self.add_query_model(Identifier, identifier_tuple_keys, identifier_tuple_extra)

        return identifier_tuple_keys

    def _set_simple_fk(self, related_field: Field, value) -> tuple:
        value = related_field.get_prep_value(value)
        if value is None:
            return ()
        return (value,), None

    def _merge_collection_attrs(
        self,
        model: type[BrowserCollectionModel],
        key_values: tuple,
        collection: Mapping,
    ) -> tuple:
        """
        Merge one comic's collection attributes into the batch's so far.

        Every comic proposes its own extra values for its collection. The
        query phase settles several proposals by set order, so the ones
        already proposed are rewritten to carry the merged attributes too
        and all proposals agree.
        """
        attr_names = COLLECTION_MODEL_ATTR_FIELDS[model]
        values = []
        for attr_name in attr_names:
            field = model._meta.get_field(attr_name)
            value = field.get_prep_value(collection.get(attr_name))
            values.append(None if value == "" else value)
        proposed = self.metadata[QUERY_MODELS].get(model, {}).get(key_values)
        if not proposed:
            return tuple(values)
        num_attrs = len(attr_names)
        for extra_values in proposed:
            old_values = extra_values[-num_attrs:]
            for index, attr_name in enumerate(attr_names):
                merge = _ATTR_MERGE.get(attr_name, max_none)
                values[index] = merge(old_values[index], values[index])
        merged = tuple(values)
        self.metadata[QUERY_MODELS][model][key_values] = {
            (*extra_values[:-num_attrs], *merged) for extra_values in proposed
        }
        return merged

    def _set_collection_tree_node(
        self,
        model: type[BrowserCollectionModel],
        name_field: Field,
        collection: dict | None,
        collection_list: list,
    ) -> tuple:
        name_key = NUMBER_KEY if model == Volume else NAME_KEY
        if collection is None:
            collection = {}

        collection_name = collection.get(name_key, model.DEFAULT_NAME)
        clean_collection_name = name_field.get_prep_value(collection_name)
        collection_list.append(clean_collection_name)
        extra_vals = []
        if model == Volume:
            number_to = collection.get(VOLUME_NUMBER_TO_KEY, model.DEFAULT_NAME)
            clean_number_to = name_field.get_prep_value(number_to)
            collection_list.append(clean_number_to)
        else:
            identifier_tuple = self.get_identifier_tuple(model, collection)
            extra_vals.append(identifier_tuple)
        key_values = tuple(collection_list)
        if COLLECTION_MODEL_ATTR_FIELDS[model]:
            extra_vals.extend(
                self._merge_collection_attrs(model, key_values, collection)
            )
        return key_values, frozenset((tuple(extra_vals),))

    def get_fk_metadata(self, md, path) -> None:
        """Aggregate Simple Foreign Keys."""
        collection_list = []
        # prevents skipped metadata from destroying browser collection links
        field_names = tuple(COLLECTION_FIELD_NAMES) + tuple(
            sorted((set(md.keys()) - _MINIMAL_KEYS) & COMIC_FK_FIELD_NAMES)
        )
        for field_name in field_names:
            related_field = COMIC_FK_FIELD_NAMES_FIELD_MAP[field_name]
            # No identifiers on many2one fks yet
            # md_key = FIELD_NAME_TO_MD_KEY_MAP.get(field_name, field_name) if they ever diverge
            model: type[BaseModel] = related_field.model  # pyright: ignore[reportAssignmentType], # ty: ignore[invalid-assignment]
            md_key = field_name
            value = md.pop(md_key, None)

            if issubclass(model, BrowserCollectionModel):
                key_values, extra_values = self._set_collection_tree_node(
                    model, related_field, value, collection_list
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

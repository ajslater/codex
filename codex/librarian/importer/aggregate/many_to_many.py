"""Aggregate ManyToMany Metadata."""

from collections.abc import Mapping
from typing import TYPE_CHECKING

from comicbox.schemas.comicbox import IDENTIFIERS_KEY, NUMBER_KEY, ROLES_KEY
from django.db.models import CharField, Field
from django.db.models.fields.related import ManyToManyField

from codex.librarian.importer.aggregate.const import (
    COMPLEX_FIELD_AGG_MAP,
    FIELD_NAME_TO_MD_KEY_MAP,
    ID_TYPE_KEY,
)
from codex.librarian.importer.aggregate.foreign_keys import (
    AggregateForeignKeyMetadataImporter,
)
from codex.librarian.importer.const import (
    COMIC_M2M_FIELDS,
    CREDITS_FIELD_NAME,
    LINK_M2MS,
    STORY_ARC_NUMBERS_FIELD_NAME,
    get_key_index,
)
from codex.models.comic import Comic
from codex.models.groups import Folder
from codex.models.identifier import IdentifierSource
from codex.models.named import CreditRole

if TYPE_CHECKING:
    from codex.models.base import BaseModel


class AggregateManyToManyMetadataImporter(AggregateForeignKeyMetadataImporter):
    """Aggregate ManyToMany Metadata."""

    def _get_m2m_metadata_dict_model_aggregate_sub_sub_value(
        self,
        field_name: str,
        sub_value_obj: Mapping | None,
        sub_sub_md_key: str,
        sub_sub_field: Field,
    ):
        # sub_sub_md_key is gonna be like identifiers or designation or roles or number
        # StoryArcNumber.number can be None.
        clean_sub_sub_values = None
        if sub_value_obj is None:
            return clean_sub_sub_values
        sub_sub_value = sub_value_obj.get(sub_sub_md_key)
        if sub_sub_value is None and field_name != STORY_ARC_NUMBERS_FIELD_NAME:
            return clean_sub_sub_values

        if sub_sub_md_key == IDENTIFIERS_KEY and sub_sub_value:
            field = Comic._meta.get_field(field_name)
            model: type[BaseModel] = field.related_model  # pyright: ignore[reportAssignmentType]
            clean_sub_sub_values = self.get_identifier_tuple(model, sub_sub_value)
        elif sub_sub_md_key == ROLES_KEY and sub_sub_value:
            clean_sub_sub_values = set()
            for sub_sub_sub_key_name, sub_sub_sub_value_obj in sub_sub_value.items():
                clean_sub_sub_sub_key_name = sub_sub_field.get_prep_value(
                    sub_sub_sub_key_name
                )
                sub_sub_key_identifier_tuple = self.get_identifier_tuple(
                    CreditRole, sub_sub_sub_value_obj
                )
                clean_sub_sub_values.add(
                    (clean_sub_sub_sub_key_name, sub_sub_key_identifier_tuple)
                )
            clean_sub_sub_values = frozenset(clean_sub_sub_values)
        else:
            clean_sub_sub_values = sub_sub_field.get_prep_value(sub_sub_value)
            if sub_sub_md_key == NUMBER_KEY:
                clean_sub_sub_values = frozenset({clean_sub_sub_values})
        return clean_sub_sub_values

    def _get_m2m_metadata_aggregate_sub_values_init(
        self,
        md_key: str,
        field_name: str,
        sub_key_name: str,
        sub_value_obj: Mapping | None,
    ):
        sub_key_name_field, sub_key_identifier_field, dict_field_keys = (
            COMPLEX_FIELD_AGG_MAP[field_name]
        )
        if isinstance(sub_key_name_field, CharField):
            clean_sub_key_name = sub_key_name_field.get_prep_value(sub_key_name)
        else:
            clean_sub_key_name = sub_key_name_field.field.get_prep_value(sub_key_name)
        if sub_value_obj and sub_key_identifier_field:
            sub_model: type[BaseModel] = sub_key_identifier_field.field.model  # pyright: ignore[reportAssignmentType]
            sub_key_identifier_tuple = self.get_identifier_tuple(
                sub_model, sub_value_obj
            )
        else:
            sub_key_identifier_tuple = None
        if sub_key_identifier_field:
            clean_sub_key = (clean_sub_key_name, sub_key_identifier_tuple)
            # adds same models
            sub_key_model = sub_key_identifier_field.field.model
        else:
            clean_sub_key = (clean_sub_key_name,)
            if md_key == IDENTIFIERS_KEY and clean_sub_key_name:
                sub_key_model = IdentifierSource
            else:
                sub_key_model = None

        if sub_key_model and clean_sub_key:
            self.add_query_model(
                sub_key_model,
                clean_sub_key,
            )
        return dict_field_keys, clean_sub_key

    def _get_m2m_metadata_dict_model_aggregate_sub_values(
        self,
        md_key: str,
        field: ManyToManyField,
        sub_key_name: str,
        sub_value_obj: Mapping | None,
    ):
        # Clean name and if there are sub values get those.
        # sub_key: story_arc_name_a,
        # sub_key: character_name_a,
        dict_field_keys, clean_sub_key = (
            self._get_m2m_metadata_aggregate_sub_values_init(
                md_key, field.name, sub_key_name, sub_value_obj
            )
        )

        clean_sub_values = []
        roles_or_numbers = set()
        for sub_sub_md_key, sub_sub_field in dict_field_keys.items():
            # Sub_sub_md_key is identifiers or designation or roles

            if sub_sub_md_key == ID_TYPE_KEY:
                # Special injection of identifier type
                clean_sub_values.append(sub_sub_field)
                continue

            # Get one sub value tuple for the aggregate tuple
            clean_sub_sub_values = (
                self._get_m2m_metadata_dict_model_aggregate_sub_sub_value(
                    field.name,
                    sub_value_obj,
                    sub_sub_md_key,
                    sub_sub_field.field,
                )
            )
            if isinstance(clean_sub_sub_values, frozenset):
                # Special multiplier for Roles
                roles_or_numbers |= clean_sub_sub_values
            else:
                clean_sub_values.append(clean_sub_sub_values)

        if roles_or_numbers:
            if field.name == CREDITS_FIELD_NAME:
                self.add_query_model(CreditRole, roles_or_numbers)
            clean_sub_key = clean_sub_key[0]
            # Remove non key values for complex type rels
            if field.name == CREDITS_FIELD_NAME:
                clean_sub_values = {(clean_sub_key, val[0]) for val in roles_or_numbers}
            else:
                clean_sub_values = {(clean_sub_key, val) for val in roles_or_numbers}
        else:
            clean_sub_values = {clean_sub_key + tuple(clean_sub_values)}
        # Create query models for complex types who's keys are other types.
        return clean_sub_values

    def _get_m2m_metadata_dict_model(
        self,
        md_key: str,
        field: ManyToManyField,
        values: Mapping | list | tuple | set | frozenset,
    ):
        # Process values dict for a field
        # {story_arc_name_a: { number: 1, identifiers: {} }, ...}
        # {character_name_a: { identifiers: {} }, ...}
        clean_values = set()
        if not isinstance(values, Mapping):
            values = dict.fromkeys(values)
        for sub_key_name, sub_value in values.items():
            clean_sub_value = self._get_m2m_metadata_dict_model_aggregate_sub_values(
                md_key, field, sub_key_name, sub_value
            )
            clean_values |= clean_sub_value

        related_model: type[BaseModel] = field.related_model
        if clean_values and related_model != Folder:
            self.add_query_model(related_model, clean_values)
        return clean_values

    def get_m2m_metadata(self, md, path):
        """Many_to_many fields get moved into a separate dict."""
        m2m_md = {}
        for field in COMIC_M2M_FIELDS:
            md_key = FIELD_NAME_TO_MD_KEY_MAP.get(field.name, field.name)
            values = md.pop(md_key, None)
            if values is None:
                continue
            if clean_values := self._get_m2m_metadata_dict_model(md_key, field, values):
                key_index = get_key_index(field.related_model)
                clean_key_values = set()
                for clean_val_tuple in clean_values:
                    clean_key_values_tuple = clean_val_tuple[:key_index]
                    deep_trimmed_key_values = []
                    for val in clean_key_values_tuple:
                        # might have to lok up index in the future but for now it's the default.
                        deep_trimmed_val = val[0] if isinstance(val, tuple) else val
                        deep_trimmed_key_values.append(deep_trimmed_val)
                    clean_key_values.add(tuple(deep_trimmed_key_values))
                if field.name not in m2m_md:
                    m2m_md[field.name] = set()
                m2m_md[field.name] |= clean_key_values

        self.metadata[LINK_M2MS][str(path)] = m2m_md

"""Aggregate ManyToMany Metadata."""

from collections.abc import Mapping
from typing import TYPE_CHECKING

from comicbox.schemas.comicbox import IDENTIFIERS_KEY, NUMBER_KEY, ROLES_KEY
from django.db.models import CharField, Field
from django.db.models.fields.related import ManyToManyField

from codex.librarian.scribe.importer.const import (
    COMIC_M2M_FIELDS,
    CREDITS_FIELD_NAME,
    IDENTIFIERS_FIELD_NAME,
    LINK_M2MS,
    STORY_ARC_NUMBERS_FIELD_NAME,
    get_key_index,
)
from codex.librarian.scribe.importer.read.const import (
    COMPLEX_FIELD_AGG_MAP,
    FIELD_NAME_TO_MD_KEY_MAP,
    ID_TYPE_KEY,
)
from codex.librarian.scribe.importer.read.foreign_keys import (
    AggregateForeignKeyMetadataImporter,
)
from codex.models.comic import Comic
from codex.models.groups import Folder
from codex.models.identifier import IdentifierSource
from codex.models.named import CreditRole

if TYPE_CHECKING:
    from codex.models.base import BaseModel


class AggregateManyToManyMetadataImporter(AggregateForeignKeyMetadataImporter):
    """Aggregate ManyToMany Metadata."""

    def _get_m2m_metadata_dict_model_aggregate_sub_sub_value_identifiers(
        self, field_name, sub_sub_value
    ):
        field = Comic._meta.get_field(field_name)
        model: type[BaseModel] = field.related_model  # pyright: ignore[reportAssignmentType], # ty: ignore[invalid-assignment]
        return self.get_identifier_tuple(model, sub_sub_value)

    def _get_m2m_metadata_dict_model_aggregate_sub_sub_value_roles(
        self, sub_sub_field, sub_sub_value
    ):
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
        return frozenset(clean_sub_sub_values)

    def _get_m2m_metadata_dict_model_aggregate_sub_sub_value(
        self,
        field_name: str,
        sub_value_obj: Mapping | None,
        sub_sub_md_key: str,
        sub_sub_field: Field,
    ):
        # sub_sub_md_key is identifiers or designation or roles or number
        # StoryArcNumber.number can be None.
        clean_sub_sub_values = None
        if sub_value_obj is None:
            return clean_sub_sub_values
        sub_sub_value = sub_value_obj.get(sub_sub_md_key)
        if sub_sub_value is None and field_name != STORY_ARC_NUMBERS_FIELD_NAME:
            return clean_sub_sub_values

        if sub_sub_md_key == IDENTIFIERS_KEY and sub_sub_value:
            clean_sub_sub_values = (
                self._get_m2m_metadata_dict_model_aggregate_sub_sub_value_identifiers(
                    field_name, sub_sub_value
                )
            )
        elif sub_sub_md_key == ROLES_KEY and sub_sub_value:
            clean_sub_sub_values = (
                self._get_m2m_metadata_dict_model_aggregate_sub_sub_value_roles(
                    sub_sub_field, sub_sub_value
                )
            )
        else:
            clean_sub_sub_values = sub_sub_field.get_prep_value(sub_sub_value)
            if sub_sub_md_key == NUMBER_KEY:
                clean_sub_sub_values = frozenset({clean_sub_sub_values})
        return clean_sub_sub_values

    def _get_m2m_metadata_aggregate_sub_values_init(
        self,
        md_key: str,
        sub_key_name_field,
        sub_key_name: str,
        sub_key_identifier_field,
        sub_value_obj,
    ):
        name_field = (
            sub_key_name_field
            if isinstance(sub_key_name_field, CharField)
            else sub_key_name_field.field
        )
        clean_sub_key_name = name_field.get_prep_value(sub_key_name)

        clean_sub_values = []
        sub_model = None
        if sub_key_identifier_field:
            sub_model = sub_key_identifier_field.field.model
            sub_key_identifier_tuple = self.get_identifier_tuple(
                sub_model, sub_value_obj
            )
            clean_sub_values.append(sub_key_identifier_tuple)
        elif md_key == IDENTIFIERS_KEY and clean_sub_key_name:
            sub_model = IdentifierSource

        clean_sub_key = (clean_sub_key_name,)
        if sub_model:
            clean_sub_values_set = (
                frozenset({tuple(clean_sub_values)}) if clean_sub_values else None
            )
            self.add_query_model(sub_model, clean_sub_key, clean_sub_values_set)
        return clean_sub_key, clean_sub_values

    def _get_roles_or_numbers(
        self, field, dict_field_keys, clean_sub_values, sub_value_obj
    ):
        roles_or_numbers = set()
        for sub_sub_md_key, sub_sub_field in dict_field_keys.items():
            # Sub_sub_md_key is identifiers or designation or roles

            if sub_sub_md_key == ID_TYPE_KEY:
                # Special injection of identifier type
                clean_sub_values.append(sub_sub_field)
                continue

            # Get one sub value tuple for the aggregate tuple
            clean_sub_sub_value = (
                self._get_m2m_metadata_dict_model_aggregate_sub_sub_value(
                    field.name,
                    sub_value_obj,
                    sub_sub_md_key,
                    sub_sub_field.field,
                )
            )
            if isinstance(clean_sub_sub_value, frozenset):
                # Special multiplier for Roles
                roles_or_numbers |= clean_sub_sub_value
            else:
                clean_sub_values.append(clean_sub_sub_value)
        return roles_or_numbers

    def _create_clean_sub_map(
        self, field, roles_or_numbers, clean_sub_key, clean_sub_values
    ):
        # Create sub_map with special provisions for complex types.
        clean_sub_map = {}
        if roles_or_numbers:
            clean_sub_key = clean_sub_key[0]
            clean_sub_map = {}
            if field.name == CREDITS_FIELD_NAME:
                # Credits
                for role_values in roles_or_numbers:
                    role_keys, role_extras = role_values
                    self.add_query_model(
                        CreditRole, (role_keys,), frozenset({(role_extras,)})
                    )
                    clean_sub_map[(clean_sub_key, role_keys)] = set()
            else:
                # StoryArcNumbers
                for role_values in roles_or_numbers:
                    clean_sub_map[(clean_sub_key, role_values)] = set()
        elif field.name == IDENTIFIERS_FIELD_NAME:
            clean_sub_key += tuple(clean_sub_values[:2])
            url_value = tuple(clean_sub_values[2:])
            clean_sub_value = frozenset({url_value})
            clean_sub_map = {clean_sub_key: clean_sub_value}
        else:
            clean_sub_value = (
                frozenset((tuple(clean_sub_values),))
                if clean_sub_values
                else frozenset()
            )
            clean_sub_map = {clean_sub_key: clean_sub_value}
        # Create query models for complex types who's keys are other types.
        return clean_sub_map

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
        sub_key_name_field, sub_key_identifier_field, dict_field_keys = (
            COMPLEX_FIELD_AGG_MAP[field.name]
        )
        clean_sub_key, clean_sub_values = (
            self._get_m2m_metadata_aggregate_sub_values_init(
                md_key,
                sub_key_name_field,
                sub_key_name,
                sub_key_identifier_field,
                sub_value_obj,
            )
        )
        roles_or_numbers = self._get_roles_or_numbers(
            field, dict_field_keys, clean_sub_values, sub_value_obj
        )
        return self._create_clean_sub_map(
            field, roles_or_numbers, clean_sub_key, clean_sub_values
        )

    def _get_m2m_metadata_dict_model(
        self,
        md_key: str,
        field: ManyToManyField,
        values: Mapping[str, Mapping | None] | list | tuple | set | frozenset,
    ):
        # Process values dict for a field
        # {story_arc_name_a: { number: 1, identifiers: {} }, ...}
        # {character_name_a: { identifiers: {} }, ...}
        clean_values_map: dict[tuple, frozenset[tuple]] = {}
        if not isinstance(values, Mapping):
            values = dict.fromkeys(values)
        for sub_key_name, sub_value in values.items():
            clean_sub_map = self._get_m2m_metadata_dict_model_aggregate_sub_values(
                md_key,
                field,
                sub_key_name,  # ty: ignore[invalid-argument-type]
                sub_value,  # ty: ignore[invalid-argument-type]
            )
            clean_values_map.update(clean_sub_map)

        related_model: type[BaseModel] = field.related_model
        if related_model != Folder:
            for key, value in clean_values_map.items():
                self.add_query_model(related_model, key, value)
        return clean_values_map

    def _get_m2m_metadata_for_field(self, field, md, m2m_md):
        md_key = FIELD_NAME_TO_MD_KEY_MAP.get(field.name, field.name)
        values = md.pop(md_key, None)
        if values is None:
            return
        if clean_values := self._get_m2m_metadata_dict_model(md_key, field, values):
            key_index = get_key_index(field.related_model)
            clean_key_values = set()
            for clean_val_tuple in clean_values:
                clean_key_values_tuple = clean_val_tuple[:key_index]
                deep_trimmed_key_values = []
                for val in clean_key_values_tuple:
                    # might have to look up index in the future but for now it's the default.
                    deep_trimmed_val = val[0] if isinstance(val, tuple) else val
                    deep_trimmed_key_values.append(deep_trimmed_val)
                clean_key_values.add(tuple(deep_trimmed_key_values))
            if field.name not in m2m_md:
                m2m_md[field.name] = set()
            m2m_md[field.name] |= clean_key_values

    def get_m2m_metadata(self, md, path):
        """Many_to_many fields get moved into a separate dict."""
        m2m_md = {}
        for field in COMIC_M2M_FIELDS:
            self._get_m2m_metadata_for_field(field, md, m2m_md)
        self.metadata[LINK_M2MS][str(path)] = m2m_md

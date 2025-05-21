"""Aggregate ManyToMany Metadata."""

from pathlib import Path
from typing import TYPE_CHECKING

from django.db.models import Field
from django.db.models.fields.related import ManyToManyField
from django.db.models.query_utils import DeferredAttribute

from codex.librarian.importer.aggregate.const import (
    DICT_MODEL_AGG_MAP,
    DICT_MODEL_SUB_MODEL,
    DICT_MODEL_SUB_SUB_KEY,
    FIELD_NAME_TO_MD_KEY_MAP,
)
from codex.librarian.importer.aggregate.foreign_keys import (
    AggregateForeignKeyMetadataImporter,
)
from codex.librarian.importer.const import (
    COMIC_M2M_FIELDS,
    FOLDERS_FIELD,
    IDENTIFIERS_FIELD_NAME,
    M2M_LINK,
    QUERY_MODELS,
    STORY_ARC_NUMBERS_FIELD_NAME,
)
from codex.models.groups import Folder
from codex.models.named import NamedModel, Universe

if TYPE_CHECKING:
    from codex.models.base import BaseModel


class AggregateManyToManyMetadataImporter(AggregateForeignKeyMetadataImporter):
    """Aggregate ManyToMany Metadata."""

    def _get_m2m_metadata_dict_model_aggregate_sub_sub_value(
        self,
        field_name: str,
        sub_value,
        sub_sub_key: str,
        sub_sub_field: DeferredAttribute,
    ):
        sub_sub_value = sub_value.get(sub_sub_key)
        # Story Arc Numbers can be None.
        if sub_sub_value is None and field_name != STORY_ARC_NUMBERS_FIELD_NAME:
            return set()
        if isinstance(sub_sub_value, dict):
            clean_sub_sub_value = {
                sub_sub_field.field.get_prep_value(sub_sub_sub_value)
                for sub_sub_sub_value in sub_sub_value
            }
        else:
            clean_sub_sub_value = {sub_sub_field.field.get_prep_value(sub_sub_value)}

        if (model := DICT_MODEL_SUB_SUB_KEY.get(sub_sub_key)) and clean_sub_sub_value:
            if model not in self.metadata[QUERY_MODELS]:
                self.metadata[QUERY_MODELS][model] = set()
            self.metadata[QUERY_MODELS][model] |= clean_sub_sub_value
        return clean_sub_sub_value

    def _get_m2m_metadata_dict_model_aggregate_sub_values(
        self, field: Field, sub_key, sub_value
    ):
        clean_sub_key = NamedModel._meta.get_field("name").get_prep_value(sub_key)
        clean_sub_value = (
            [clean_sub_key] if field.name == IDENTIFIERS_FIELD_NAME else set()
        )
        dict_model_key_fields = DICT_MODEL_AGG_MAP[field.name]
        for sub_sub_key, sub_sub_field in dict_model_key_fields.items():
            clean_sub_sub_value = (
                self._get_m2m_metadata_dict_model_aggregate_sub_sub_value(
                    field.name,
                    sub_value,
                    sub_sub_key,
                    sub_sub_field,
                )
            )
            if isinstance(clean_sub_value, list):
                clean_sub_value.append(next(iter(clean_sub_sub_value)))
            else:
                clean_sub_value = {(clean_sub_key, val) for val in clean_sub_sub_value}
        if isinstance(clean_sub_value, list):
            clean_sub_value = {
                tuple(clean_sub_value),
            }
        related_model: type[BaseModel] = field.related_model  # pyright: ignore[reportAssignmentType]
        if clean_sub_key is not None and (
            key_model := DICT_MODEL_SUB_MODEL.get(related_model)
        ):
            if key_model not in self.metadata[QUERY_MODELS]:
                self.metadata[QUERY_MODELS][key_model] = set()
            self.metadata[QUERY_MODELS][key_model].add(clean_sub_key)
        return clean_sub_value

    def _get_m2m_metadata_dict_model(self, field: Field, value):
        clean_values = set()
        for sub_key, sub_value in value.items():
            clean_sub_value = self._get_m2m_metadata_dict_model_aggregate_sub_values(
                field, sub_key, sub_value
            )
            clean_values |= clean_sub_value

        model = field.related_model
        if model not in self.metadata[QUERY_MODELS]:
            self.metadata[QUERY_MODELS][model] = set()
        self.metadata[QUERY_MODELS][model] |= clean_values
        return clean_values

    def _get_m2m_metadata_clean(self, field: ManyToManyField, value):
        """Clean a simple named value."""
        model = field.related_model
        clean_value = {
            model._meta.get_field("name").get_prep_value(sub_key) for sub_key in value
        }
        if clean_value and model != Folder:
            if model not in self.metadata[QUERY_MODELS]:
                self.metadata[QUERY_MODELS][model] = set()
            self.metadata[QUERY_MODELS][model] |= frozenset(clean_value)
        return clean_value

    def get_m2m_metadata(self, md, path):
        """Many_to_many fields get moved into a separate dict."""
        m2m_md = {}
        for field in COMIC_M2M_FIELDS:
            md_key = FIELD_NAME_TO_MD_KEY_MAP.get(field.name, field.name)
            value = md.pop(md_key, None)
            if value is None:
                continue
            clean_method = (
                self._get_m2m_metadata_dict_model
                if field.name in DICT_MODEL_AGG_MAP
                else self._get_m2m_metadata_clean
            )
            if clean_value := clean_method(field, value):
                if field.name not in m2m_md:
                    m2m_md[field.name] = set()

                if field.related_model == Universe:
                    # Specially turn universe into a regular named model for linking
                    clean_value = {value[0] for value in clean_value}

                m2m_md[field.name] |= clean_value

        parents = tuple(str(parent) for parent in Path(path).parents)
        m2m_md[FOLDERS_FIELD] = parents
        self.metadata[M2M_LINK][str(path)] = m2m_md

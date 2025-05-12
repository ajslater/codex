"""Aggregate ManyToMany Metadata."""

from pathlib import Path

from comicbox.schemas.comicbox import ARCS_KEY, IDENTIFIERS_KEY
from django.db.models.fields.related import ManyToManyField
from django.db.models.query_utils import DeferredAttribute

from codex.librarian.importer.aggregate.const import (
    DICT_MODEL_AGG_MAP,
    DICT_MODEL_FOR_VALUE,
    DICT_MODEL_SUB_FIELDS,
    FIELD_NAME_TO_MD_KEY_MAP,
)
from codex.librarian.importer.aggregate.foreign_keys import (
    AggregateForeignKeyMetadataImporter,
)
from codex.librarian.importer.const import (
    COMIC_M2M_FIELD_NAMES,
    FOLDERS_FIELD,
    M2M_LINK,
    QUERY_MODELS,
)
from codex.models.groups import Folder
from codex.models.named import NamedModel


class AggregateManyToManyMetadataImporter(AggregateForeignKeyMetadataImporter):
    """Aggregate ManyToMany Metadata."""

    def _get_m2m_metadata_dict_model_sub_fields(
        self,
        sub_value,
        sub_sub_key: str,
        sub_sub_field: DeferredAttribute,
        md_key: str,
    ):
        sub_sub_value = sub_value.get(sub_sub_key)
        if sub_sub_value is None:
            return set()
        if isinstance(sub_sub_value, dict):
            clean_sub_sub_value = {
                sub_sub_field.field.get_prep_value(sub_sub_sub_value)
                for sub_sub_sub_value in sub_sub_value
            }
        else:
            clean_sub_sub_value = {sub_sub_field.field.get_prep_value(sub_sub_value)}
        if clean_sub_sub_value or md_key == ARCS_KEY:
            model = DICT_MODEL_SUB_FIELDS.get(sub_sub_key)
            if model:
                if model not in self.metadata[QUERY_MODELS]:
                    self.metadata[QUERY_MODELS][model] = set()
                self.metadata[QUERY_MODELS][model] |= clean_sub_sub_value
        return clean_sub_sub_value

    def _get_m2m_metadata_dict_model(
        self, value, dict_model_key_fields: dict, md_key: str
    ):
        clean_value = set()
        for sub_key, sub_value in value.items():
            clean_sub_key = NamedModel._meta.get_field("name").get_prep_value(sub_key)
            clean_sub_value = [clean_sub_key] if md_key == IDENTIFIERS_KEY else set()
            for sub_sub_key, sub_sub_field in dict_model_key_fields.items():
                clean_sub_sub_value = self._get_m2m_metadata_dict_model_sub_fields(
                    sub_value,
                    sub_sub_key,
                    sub_sub_field,
                    md_key,
                )
                if isinstance(clean_sub_value, list):
                    clean_sub_value.append(next(iter(clean_sub_sub_value)))
                else:
                    clean_sub_value = {
                        (clean_sub_key, val) for val in clean_sub_sub_value
                    }
            if clean_sub_key is not None:
                key_model = DICT_MODEL_SUB_FIELDS.get(md_key)
                if key_model not in self.metadata[QUERY_MODELS]:
                    self.metadata[QUERY_MODELS][key_model] = set()
                self.metadata[QUERY_MODELS][key_model].add(clean_sub_key)
            if isinstance(clean_sub_value, list):
                clean_sub_value = tuple(clean_sub_value)
                clean_value.add(clean_sub_value)
            else:
                clean_value |= clean_sub_value

        value_model = DICT_MODEL_FOR_VALUE.get(md_key)
        if value_model not in self.metadata[QUERY_MODELS]:
            self.metadata[QUERY_MODELS][value_model] = set()
        query_model_values = (
            {next(iter(clean_value))[0]} if md_key == IDENTIFIERS_KEY else clean_value
        )
        self.metadata[QUERY_MODELS][value_model] |= query_model_values
        return clean_value

    def _get_m2m_metadata_clean(self, field: ManyToManyField, value):
        clean_value = {
            field.related_model._meta.get_field("name").get_prep_value(sub_key)
            for sub_key in value
        }
        if clean_value and field.model != Folder:
            if field.model not in self.metadata[QUERY_MODELS]:
                self.metadata[QUERY_MODELS][field.related_model] = set()
            self.metadata[QUERY_MODELS][field.related_model] |= frozenset(clean_value)
        return clean_value

    def get_m2m_metadata(self, md, path):
        """Many_to_many fields get moved into a separate dict."""
        m2m_md = {}
        for field in COMIC_M2M_FIELD_NAMES:
            md_key = FIELD_NAME_TO_MD_KEY_MAP.get(field.name, field.name)
            value = md.pop(md_key, None)
            if value is None:
                continue
            if dict_model_key_fields := DICT_MODEL_AGG_MAP.get(field.name):
                clean_value = self._get_m2m_metadata_dict_model(
                    value, dict_model_key_fields, md_key
                )
            else:
                clean_value = self._get_m2m_metadata_clean(field, value)
            if clean_value:
                if field.name not in m2m_md:
                    m2m_md[field.name] = set()
                m2m_md[field.name] |= clean_value

        parents = tuple(str(parent) for parent in Path(path).parents)
        m2m_md[FOLDERS_FIELD] = parents
        self.metadata[M2M_LINK][str(path)] = m2m_md

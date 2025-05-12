"""Aggregate metadata from comcs to prepare for importing."""

from pathlib import Path
from tarfile import TarError
from types import MappingProxyType
from zipfile import BadZipFile, LargeZipFile

from comicbox.box import Comicbox
from comicbox.config import get_config
from comicbox.exceptions import UnsupportedArchiveTypeError
from comicbox.schemas.comicbox import (
    ARCS_KEY,
    COVER_DATE_KEY,
    DATE_KEY,
    IDENTIFIERS_KEY,
    NAME_KEY,
    NUMBER_KEY,
    STORE_DATE_KEY,
    STORIES_KEY,
    SUFFIX_KEY,
)
from django.db.models.fields.related import ManyToManyField
from django.db.models.query_utils import DeferredAttribute
from py7zr.exceptions import ArchiveError as Py7zError
from rarfile import Error as RarError

from codex.librarian.importer.const import (
    COMIC_FK_FIELD_NAMES,
    COMIC_M2M_FIELD_NAMES,
    COMIC_PATHS,
    COMIC_VALUES,
    COUNT_FIELDS,
    DICT_MODEL_AGG_MAP,
    DICT_MODEL_FOR_VALUE,
    DICT_MODEL_SUB_FIELDS,
    FIELD_NAME_TO_MD_KEY_MAP,
    FIS,
    FK_LINK,
    FOLDERS_FIELD,
    GROUP_TREES,
    M2M_LINK,
    QUERY_MODELS,
)
from codex.librarian.importer.query_fks import QueryForeignKeysImporter
from codex.librarian.importer.status import ImportStatusTypes
from codex.models.admin import AdminFlag
from codex.models.groups import BrowserGroupModel, Folder
from codex.models.named import NamedModel
from codex.settings.settings import LOGLEVEL
from codex.status import Status
from codex.util import max_none

_COMICBOX_CONFIG = get_config(
    {
        "compute_pages": False,
        "loglevel": LOGLEVEL,
    }
)
_BROWSER_GROUPS_MAP = MappingProxyType(
    {
        cls: (cls.__name__.lower(), cls.name.field)  # pyright: ignore[reportAttributeAccessIssue]
        for cls in COUNT_FIELDS
    }
)
EMPTY_GROUP_TREES = MappingProxyType({GROUP_TREES: {cls: {} for cls in COUNT_FIELDS}})
_UNUSED_COMICBOX_FIELDS = (
    "alternate_images",
    "bookmark",
    "credit_primaries",
    "ext",
    "manga",
    "pages",
    "prices",  # add
    "protagonist",  # add
    "remainders",
    "reprints",  # add
    "universes",  # add
    "updated_at",
)


class AggregateMetadataImporter(QueryForeignKeysImporter):
    """Aggregate metadata from comics to prepare for importing."""

    @staticmethod
    def _extract_clean_md(md):
        for key in _UNUSED_COMICBOX_FIELDS:
            md.pop(key, None)

    @staticmethod
    def _extract_transform(md):
        if date := md.pop(DATE_KEY, None):
            date.pop(COVER_DATE_KEY, None)
            date.pop(STORE_DATE_KEY, None)
            md.update(date)

        if issue := md.pop("issue", None):
            if name := issue.pop(NAME_KEY, None):
                issue["issue"] = name
            if number := issue.pop(NUMBER_KEY, None):
                issue["issue_number"] = number
            if suffix := issue.pop(SUFFIX_KEY, None):
                issue["issue_suffix"] = suffix
            md.update(issue)

        if stories := md.pop(STORIES_KEY, None):
            md["name"] = "; ".join(stories)

    @staticmethod
    def _set_group_tree_group(
        attrs: tuple,
        md: dict,
        group_cls: type[BrowserGroupModel],
        groups_md: dict,
        group_tree: list,
    ):
        group_field_name, field = attrs
        group = md.pop(group_field_name, {})
        group_name = group.get("name", group_cls.DEFAULT_NAME)
        group_name = field.get_prep_value(group_name)
        if (count_key := COUNT_FIELDS.get(group_cls)) and (
            count := group.get(count_key)
        ):
            groups_md[count_key] = count
        group_tree.append(group_name)

    def _set_group_tree_max_group_count(  # noqa: PLR0913
        self,
        path,
        group_tree,
        group_md,
        group_class,
        index: int,
        count_key: str | None = None,
    ):
        """Assign the maximum group count number."""
        group_name = group_tree[0:index]
        if count_key:
            try:
                count = max_none(
                    self.metadata[QUERY_MODELS].get(group_class, {}).get(group_name),
                    group_md.get(count_key),
                )
            except Exception:
                count = None
        else:
            count = None

        group = {group_name: count}
        # Update is fine because count max merge happens above
        if group_class not in self.metadata[QUERY_MODELS]:
            self.metadata[QUERY_MODELS][group_class] = {}
        self.metadata[QUERY_MODELS][group_class].update(group)
        field_name = group_class.__name__.lower()
        self.metadata[FK_LINK][path][field_name] = group

    def _get_group_tree(self, md, path):
        """Create the group tree to counts map for a single comic."""
        # Create group tree
        group_tree = []
        groups_md = {}
        for group_class, attrs in _BROWSER_GROUPS_MAP.items():
            self._set_group_tree_group(
                attrs,
                md,
                group_class,
                groups_md,
                group_tree,
            )

        group_tree = tuple(group_tree)

        # Aggregate into fks
        # query and create from group_trees
        index = 1
        for group_class, count_field_name in COUNT_FIELDS.items():
            self._set_group_tree_max_group_count(
                path, group_tree, groups_md, group_class, index, count_field_name
            )
            index += 1

    def _get_fk_metadata(self, md, path):
        for field_name, related_field in COMIC_FK_FIELD_NAMES.items():
            value = md.pop(field_name, None)
            if value is None:
                continue
            value = related_field.get_prep_value(value)

            if field_name not in self.metadata[QUERY_MODELS]:
                self.metadata[QUERY_MODELS][related_field.model] = set()
            self.metadata[QUERY_MODELS][related_field.model].add(value)
            self.metadata[FK_LINK][path][field_name] = value

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

    def _get_m2m_metadata(self, md, path):
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

    def _aggregate_path(self, md, path, status):
        """Aggregate metadata for one path."""
        self.metadata[FK_LINK][path] = {}
        self._get_group_tree(md, path)
        self._get_fk_metadata(md, path)
        self._get_m2m_metadata(md, path)
        if md:
            self.metadata[COMIC_VALUES][str(path)] = md
        if status:
            status.complete += 1
            self.status_controller.update(status)

    def extract(self, path, *, import_metadata: bool):
        """Extract metadata from comic and clean it for codex."""
        md = {}
        failed_import = {}
        try:
            if import_metadata:
                with Comicbox(path, config=_COMICBOX_CONFIG) as cb:
                    md = cb.to_dict()
                    md = md.get("comicbox", {})
                    md["file_type"] = cb.get_file_type()
            md["path"] = path
            self._extract_clean_md(md)
            self._extract_transform(md)
        except (
            UnsupportedArchiveTypeError,
            BadZipFile,
            LargeZipFile,
            RarError,
            Py7zError,
            TarError,
            OSError,
        ) as exc:
            self.log.warning(f"Failed to import {path}: {exc}")
            failed_import = {path: exc}
        except Exception as exc:
            self.log.exception(f"Failed to import: {path}")
            failed_import = {path: exc}
        if failed_import:
            self.metadata[FIS].update(failed_import)
        return md

    def get_aggregate_metadata(
        self,
        status=None,
    ):
        """Get aggregated metadata for the paths given."""
        all_paths = self.task.files_modified | self.task.files_created
        total_paths = len(all_paths)

        if not total_paths:
            return 0
        self.log.info(
            f"Reading tags from {total_paths} comics in {self.library.path}..."
        )
        status = Status(ImportStatusTypes.AGGREGATE_TAGS, 0, total_paths)
        self.status_controller.start(status, notify=False)

        # Set import_metadata flag
        if self.task.force_import_metadata:
            import_metadata = True
        else:
            key = AdminFlag.FlagChoices.IMPORT_METADATA.value
            import_metadata = AdminFlag.objects.get(key=key).on
        if not import_metadata:
            self.log.warning("Admin flag set to NOT import metadata.")

        # Init metadata, extract and aggregate
        self.metadata[COMIC_VALUES] = {}
        self.metadata[M2M_LINK] = {}
        self.metadata[QUERY_MODELS] = {}
        self.metadata[FK_LINK] = {}
        self.metadata[FIS] = {}
        for path in all_paths:
            if md := self.extract(path, import_metadata=import_metadata):
                self._aggregate_path(md, path, status)

        # Aggregate further
        self.metadata[QUERY_MODELS][COMIC_PATHS] = frozenset(
            self.metadata[COMIC_VALUES].keys()
        )
        fis = self.metadata[FIS]
        self.task.files_modified -= fis.keys()
        self.task.files_created -= fis.keys()

        # Set statii
        fi_status = Status(ImportStatusTypes.FAILED_IMPORTS, 0, len(fis))
        self.status_controller.update(
            fi_status,
            notify=False,
        )
        count = status.complete if status else 0
        self.log.info(f"Aggregated tags from {count} comics.")

        self.status_controller.finish(status)
        return count

"""Aggregate metadata from comcs to prepare for importing."""

from collections.abc import Mapping
from pathlib import Path

from codex.librarian.importer.const import (
    COMIC_FK_FIELD_NAMES,
    COMIC_M2M_FIELD_NAMES,
    COMIC_PATHS,
    COUNT_FIELDS,
    DICT_MODEL_AGG_MAP,
    FIS,
    FKS,
    FOLDERS_FIELD,
    GROUP_TREES,
    ISSUE_COUNT,
    M2M_MDS,
    MDS,
    VOLUME_COUNT,
)
from codex.librarian.importer.extract import ExtractMetadataImporter
from codex.librarian.importer.status import ImportStatusTypes
from codex.models import Imprint, Publisher, Series, Volume
from codex.models.admin import AdminFlag
from codex.status import Status
from codex.util import max_none


class AggregateMetadataImporter(ExtractMetadataImporter):
    """Aggregate metadata from comics to prepare for importing."""

    _BROWSER_GROUPS = (Publisher, Imprint, Series, Volume)
    _AGGREGATE_M2M_FIELD_NAMES = (COMIC_M2M_FIELD_NAMES - {"story_arc_numbers"}) | {
        "story_arcs"
    }

    @staticmethod
    def _get_structured_group(md, group_cls, group_field, groups_md):
        group = md.get(group_field, {})
        group_name = group.get("name", group_cls.DEFAULT_NAME)
        count_key = COUNT_FIELDS[group_cls]
        if count := group.get(count_key):
            groups_md[count_key] = count
        return group_name

    @classmethod
    def _get_group_tree(cls, md):
        """Create the group tree to counts map for a single comic."""
        # Create group tree
        group_tree = []
        groups_md = {}
        for group_cls in cls._BROWSER_GROUPS:
            group_field = group_cls.__name__.lower()
            if group_cls in COUNT_FIELDS:
                group_name = cls._get_structured_group(
                    md, group_cls, group_field, groups_md
                )
            else:
                group_name = md.get(group_field, group_cls.DEFAULT_NAME)

            # This fixes no imprint or whatever being in md
            md[group_field] = group_name
            group_tree.append(group_name)

        return {tuple(group_tree): groups_md}

    @classmethod
    def _get_fk_metadata(cls, md):
        fk_md = {}
        for field in COMIC_FK_FIELD_NAMES:
            if value := md.get(field):
                fk_md[field] = value
        return fk_md

    @classmethod
    def _get_m2m_metadata(cls, md, path):
        """Many_to_many fields get moved into a separate dict."""
        m2m_md = {}
        for field in cls._AGGREGATE_M2M_FIELD_NAMES:
            if value := md.pop(field, None):
                m2m_md[field] = value
        m2m_md[FOLDERS_FIELD] = Path(path).parents
        return m2m_md

    def _get_path_metadata(self, md, path):
        """Get the metadata from comicbox and munge it a little."""
        group_tree_md = self._get_group_tree(md)
        fk_md = self._get_fk_metadata(md)
        m2m_md = self._get_m2m_metadata(md, path)

        return md, m2m_md, fk_md, group_tree_md

    @staticmethod
    def _aggregate_m2m_metadata_dict_value(names, key, values, all_fks):
        field_name, key_field_name, value_field_name = names
        if not key:
            return
        all_fks[key_field_name].add(key)
        if key not in all_fks[field_name]:
            all_fks[field_name][key] = set()
        if value_field_name:
            values_set = frozenset(filter(None, values))
            if values_set:
                all_fks[field_name][key] |= values_set
                all_fks[value_field_name] |= values_set
        else:
            # Be sure to add Nones to StoryArcNumbers
            if isinstance(values, Mapping):
                added_values = tuple(values.items())
            else:
                added_values = values
            all_fks[field_name][key].add(added_values)

    @classmethod
    def _aggregate_m2m_metadata_dict(cls, field_name, value_dict, all_fks):
        """Aggregate value dicts."""
        if not field_name:
            return

        key_field_name, value_field_name = DICT_MODEL_AGG_MAP[field_name]

        if field_name not in all_fks:
            all_fks[field_name] = {}
            all_fks[key_field_name] = set()
            if value_field_name:
                all_fks[value_field_name] = set()

        names = field_name, key_field_name, value_field_name
        for key, values in value_dict.items():
            cls._aggregate_m2m_metadata_dict_value(names, key, values, all_fks)

    @classmethod
    def _aggregate_m2m_metadata(cls, all_m2m_mds, m2m_md, all_fks, path):
        """Aggregate many to many metadata by path."""
        # m2m fields and fks
        all_m2m_mds[path] = m2m_md
        # aggregate fks
        for field, names in m2m_md.items():
            if field in DICT_MODEL_AGG_MAP:
                cls._aggregate_m2m_metadata_dict(field, names, all_fks)
            elif field != FOLDERS_FIELD:
                filtered_names = filter(None, names)
                if not filtered_names:
                    continue
                if field not in all_fks:
                    all_fks[field] = set()
                all_fks[field] |= frozenset(filtered_names)

    @classmethod
    def _aggregate_fk_metadata(cls, all_fks, md):
        """Aggregate non group foreign key metadata."""
        for field, name in md.items():
            if field not in all_fks:
                all_fks[field] = set()
            all_fks[field].add(name)

    @classmethod
    def _set_max_group_count(cls, common_args, group_class, index, count_key):
        """Assign the maximum group count number."""
        all_fks, group_tree, group_md = common_args
        group_name = group_tree[0:index]
        try:
            count = max_none(
                all_fks[GROUP_TREES][Series].get(group_name),
                group_md.get(count_key),
            )
        except Exception:
            count = None
        all_fks[GROUP_TREES][group_class][group_name] = count

    @classmethod
    def _aggregate_group_tree_metadata(cls, all_fks, group_tree_md):
        """Aggregate group tree data by class."""
        for group_tree, group_md in group_tree_md.items():
            all_fks[GROUP_TREES][Publisher][group_tree[0:1]] = None
            all_fks[GROUP_TREES][Imprint][group_tree[0:2]] = None
            common_args = (all_fks, group_tree, group_md)
            cls._set_max_group_count(common_args, Series, 3, VOLUME_COUNT)
            cls._set_max_group_count(common_args, Volume, 4, ISSUE_COUNT)

    def _aggregate_path(self, md, path, status):
        """Aggregate metadata for one path."""
        md, m2m_md, fk_md, group_tree_md = self._get_path_metadata(md, path)

        path_str = str(path)
        if md:
            all_mds = self.metadata[MDS]
            all_mds[path_str] = md

        all_fks = self.metadata[FKS]
        if m2m_md:
            all_m2m_mds = self.metadata[M2M_MDS]
            self._aggregate_m2m_metadata(all_m2m_mds, m2m_md, all_fks, path_str)

        if fk_md:
            self._aggregate_fk_metadata(all_fks, fk_md)

        if group_tree_md:
            self._aggregate_group_tree_metadata(all_fks, group_tree_md)

        if status:
            status.complete += 1
            self.status_controller.update(status)

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
            key = AdminFlag.FlagChoices.IMPORT_METADATA.value  # type: ignore
            import_metadata = AdminFlag.objects.get(key=key).on
        if not import_metadata:
            self.log.warn("Admin flag set to NOT import metadata.")

        # Init metadata, extract and aggregate
        self.metadata[MDS] = {}
        self.metadata[M2M_MDS] = {}
        self.metadata[FKS] = {GROUP_TREES: {cls: {} for cls in self._BROWSER_GROUPS}}
        self.metadata[FIS] = {}
        for path in all_paths:
            md = self.extract_and_clean(path, import_metadata)
            if md:
                self._aggregate_path(md, path, status)

        # Aggregate further
        self.metadata[FKS][COMIC_PATHS] = frozenset(self.metadata[MDS].keys())
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

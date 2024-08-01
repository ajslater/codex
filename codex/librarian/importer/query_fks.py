"""Query the missing foreign keys for comics and contributors."""

from itertools import chain
from logging import DEBUG, INFO
from pathlib import Path
from types import MappingProxyType

from django.db.models import Q

from codex.librarian.importer.const import (
    COMIC_PATHS,
    CONTRIBUTORS_FIELD_NAME,
    COUNT_FIELDS,
    DICT_MODEL_CLASS_FIELDS_MAP,
    DICT_MODEL_FIELD_MODEL_MAP,
    DICT_MODEL_REL_MAP,
    FK_CREATE,
    FKC_CONTRIBUTORS,
    FKC_CREATE_FKS,
    FKC_CREATE_GROUPS,
    FKC_FOLDER_PATHS,
    FKC_IDENTIFIERS,
    FKC_STORY_ARC_NUMBERS,
    FKC_TOTAL_FKS,
    FKC_UPDATE_GROUPS,
    FKS,
    GROUP_COMPARE_FIELDS,
    GROUP_TREES,
    IDENTIFIERS_FIELD_NAME,
    IMPRINT,
    PARENT_FOLDER,
    PUBLISHER,
    SERIES,
    STORY_ARCS_METADATA_KEY,
)
from codex.librarian.importer.query_covers import QueryCustomCoversImporter
from codex.librarian.importer.status import ImportStatusTypes
from codex.logger.logging import get_logger
from codex.models import (
    Comic,
    Contributor,
    Folder,
    Imprint,
    Publisher,
    Series,
    StoryArcNumber,
    Volume,
)
from codex.models.named import Identifier
from codex.settings.settings import FILTER_BATCH_SIZE
from codex.status import Status

_CLASS_QUERY_FIELDS_MAP = MappingProxyType(
    {
        Contributor: ("role__name", "person__name"),
        StoryArcNumber: ("story_arc__name", "number"),
        Folder: ("path",),
        Imprint: ("publisher__name", "name"),
        Series: ("publisher__name", "imprint__name", "name"),
        Volume: ("publisher__name", "imprint__name", "series__name", "name"),
        Identifier: ("identifier_type__name", "nss"),
    }
)
_DEFAULT_QUERY_FIELDS = ("name",)
_EXTRA_UPDATE_FIELDS_MAP = MappingProxyType(
    {Series: ("volume_count",), Volume: ("issue_count",)}
)
_DICT_MODEL_KEY_MAP = MappingProxyType(
    {
        CONTRIBUTORS_FIELD_NAME: FKC_CONTRIBUTORS,
        STORY_ARCS_METADATA_KEY: FKC_STORY_ARC_NUMBERS,
        IDENTIFIERS_FIELD_NAME: FKC_IDENTIFIERS,
    }
)
LOG = get_logger(__name__)


class QueryForeignKeysImporter(QueryCustomCoversImporter):
    """Methods for querying what fks are missing."""

    def _get_query_fks_totals(self):
        """Get the query foreign keys totals."""
        fks_total = 0
        for key, objs in self.metadata[FKS].items():
            if key == GROUP_TREES:
                for groups in objs.values():
                    fks_total += len(groups)
            else:
                fks_total += len(objs)
        return fks_total

    @staticmethod
    def _query_existing_mds(fk_cls, fk_filter, extra_fields=None):
        """Query existing metatata tables."""
        fields = _CLASS_QUERY_FIELDS_MAP.get(fk_cls, _DEFAULT_QUERY_FIELDS)
        if extra_fields:
            fields += extra_fields
        flat = len(fields) == 1 and fk_cls != Publisher
        qs = fk_cls.objects.filter(fk_filter).values_list(*fields, flat=flat)
        return frozenset(qs)

    def _query_create_metadata(  # noqa: PLR0913
        self,
        fk_cls,
        create_mds,
        update_mds,
        q_obj: Q,
        status,
        and_q_obj: Q | None = None,
    ):
        """Get create metadata by comparing proposed meatada to existing rows."""
        vnp = fk_cls._meta.verbose_name_plural.title()
        status.subtitle = vnp
        offset = 0
        num_qs = len(q_obj.children)
        while offset < num_qs:
            # Do this in batches so as not to exceed the sqlite 1k expression tree depth limit
            # django.db.utils.OperationalError: Expression tree is too large (maximum depth 1000)
            children_chunk = q_obj.children[offset : offset + FILTER_BATCH_SIZE]
            filter_chunk = Q(*children_chunk, _connector=Q.OR)
            if and_q_obj:
                filter_chunk = and_q_obj & filter_chunk

            existing_mds = self._query_existing_mds(fk_cls, filter_chunk)
            create_mds.difference_update(existing_mds)
            if extra_update_fields := _EXTRA_UPDATE_FIELDS_MAP.get(fk_cls):
                # The mds that are in the existing_mds, but don't match the proposed mds with the extra update fields
                update_mds.update(existing_mds)
                match_with_extra_fields_mds = self._query_existing_mds(
                    fk_cls, filter_chunk, extra_update_fields
                )
                update_mds.difference_update(match_with_extra_fields_mds)

            status.add_complete(len(filter_chunk))
            self.status_controller.update(status)

            offset += FILTER_BATCH_SIZE

        status.subtitle = ""

        return num_qs

    ##########
    # GROUPS #
    ##########

    _HAS_IMPRINT_LINKS = frozenset({Series, Volume})
    _HAS_PUBLISHER_LINKS = frozenset({Imprint} | _HAS_IMPRINT_LINKS)

    @staticmethod
    def _add_parent_group_filter(
        filter_args: dict[str, str | None],
        group_name: str | None,
        field_name: str,
    ):
        """Get the parent group filter by name."""
        key = f"{field_name}__" if field_name else ""
        key += "name"

        filter_args[key] = group_name

    def _get_create_group_set(
        self, groups, group_cls, create_group_set, update_group_set, status
    ):
        """Create the create group set."""
        all_filters = Q()
        for group_tree in groups:
            filter_args: dict[str, str | None] = {}
            self._add_parent_group_filter(filter_args, group_tree[-1], "")
            if group_cls in self._HAS_PUBLISHER_LINKS:
                self._add_parent_group_filter(filter_args, group_tree[0], PUBLISHER)
            if group_cls in self._HAS_IMPRINT_LINKS:
                self._add_parent_group_filter(filter_args, group_tree[1], IMPRINT)
            if group_cls == Volume:
                self._add_parent_group_filter(filter_args, group_tree[2], SERIES)

            all_filters |= Q(**filter_args)

        candidate_groups = set(groups.keys())
        update_groups = set()
        count = self._query_create_metadata(
            group_cls, candidate_groups, update_groups, all_filters, status
        )
        create_group_set.update(candidate_groups)
        update_group_set.update(update_groups)
        return count

    def _update_action_group(
        self, group_cls, action_groups_key, group_tree, count_value: int | None
    ):
        """Update the create or update group dict with the count dict."""
        action_groups = self.metadata[FK_CREATE][action_groups_key]
        if group_cls not in action_groups:
            action_groups[group_cls] = {}
        if group_tree not in action_groups[group_cls]:
            action_groups[group_cls][group_tree] = {}
        action_groups[group_cls][group_tree] = count_value

    def _query_group_tree(self, data, group_tree, count_value: int | None):
        """Query missing groups for one group tree depth."""
        (
            create_group_set,
            update_group_set,
            group_cls,
            status,
        ) = data
        if group_tree in create_group_set:
            self._update_action_group(
                group_cls,
                FKC_CREATE_GROUPS,
                group_tree,
                count_value,
            )
        elif group_cls in update_group_set:
            # This always updates Volume or Series
            self._update_action_group(
                group_cls,
                FKC_UPDATE_GROUPS,
                group_tree,
                count_value,
            )
        status.add_complete(1)

    @staticmethod
    def _prune_group_updates_get_filter(group_cls, update_group_trees):
        """Construct the big filter for groups."""
        count_field_name = COUNT_FIELDS[group_cls]
        compare_fields = GROUP_COMPARE_FIELDS[group_cls]

        group_filter = Q()
        for group_tree, count_value in update_group_trees.items():
            compare_filter = {}
            for field_name, value in zip(compare_fields, group_tree, strict=False):
                compare_filter[field_name] = value
            compare_filter[count_field_name] = count_value
            group_filter |= Q(**compare_filter)
        return group_filter

    @staticmethod
    def _prune_group_updates_get_exists(group_cls, group_filter):
        """Query the db to create an exists_dict for comparison."""
        count_field_name = COUNT_FIELDS[group_cls]
        compare_fields = GROUP_COMPARE_FIELDS[group_cls]

        exist_dict = {}
        offset = 0
        num_qs = len(group_filter.children)
        while offset < num_qs:
            # Do this in batches so as not to exceed the 1k line sqlite limit
            children_chunk = group_filter.children[offset : offset + FILTER_BATCH_SIZE]
            filter_chunk = Q(*children_chunk, _connector=Q.OR)

            existing = group_cls.objects.filter(filter_chunk).values_list(
                *compare_fields, count_field_name
            )
            for exist_tuple in existing:
                exist_tree = tuple(exist_tuple[:-1])
                exist_dict[exist_tree] = exist_tuple[-1]

            offset += FILTER_BATCH_SIZE
        return exist_dict

    @staticmethod
    def _prune_group_updates_get_pruned_trees(update_group_trees, exist_dict):
        """Create the pruned group_trees and replace the existing one."""
        pruned_update_group_trees = {}
        for group_tree, child_count_value in update_group_trees.items():
            count_value = exist_dict.get(group_tree)
            if child_count_value == count_value:
                continue
            pruned_update_group_trees[group_tree] = child_count_value
        return pruned_update_group_trees

    def _prune_group_updates(self, group_cls, update_groups):
        """Prune groups that don't need an update."""
        update_group_trees = update_groups.get(group_cls)
        if not update_group_trees:
            return

        group_filter = self._prune_group_updates_get_filter(
            group_cls, update_group_trees
        )
        exist_dict = self._prune_group_updates_get_exists(group_cls, group_filter)
        pruned_update_group_trees = self._prune_group_updates_get_pruned_trees(
            update_group_trees, exist_dict
        )
        update_groups[group_cls] = pruned_update_group_trees

        vnp = group_cls._meta.verbose_name_plural.title()
        prune_count = len(update_group_trees) - len(pruned_update_group_trees)
        self.log.debug(f"Pruned {prune_count} {vnp} from updates.")

    def _query_missing_group(
        self,
        groups,
        group_cls,
        status,
    ):
        """Get missing groups from proposed groups to create."""
        count = 0
        if not groups:
            return count

        vnp = group_cls._meta.verbose_name_plural.title()
        status.subtitle = vnp

        create_group_set = set()
        update_group_set = set()
        self._get_create_group_set(
            groups, group_cls, create_group_set, update_group_set, status
        )

        data = (
            create_group_set,
            update_group_set,
            group_cls,
            status,
        )
        for group_tree, count_value in groups.items():
            self._query_group_tree(data, group_tree, count_value)
        self.status_controller.update(status)

        # after counts have been tallied, prune the ones that don't need an update.
        update_groups = self.metadata[FK_CREATE][FKC_UPDATE_GROUPS]
        self._prune_group_updates(group_cls, update_groups)

        status.subtitle = ""

        create_count = len(
            self.metadata[FK_CREATE][FKC_CREATE_GROUPS].get(group_cls, {})
        )
        update_count = len(
            self.metadata[FK_CREATE][FKC_UPDATE_GROUPS].get(group_cls, {})
        )
        count = create_count + update_count
        if count:
            vnp = group_cls._meta.verbose_name_plural.title()
            if create_count:
                self.log.info(f"Prepared {create_count} {vnp} for creation.")
            if update_count:
                self.log.info(f"Prepared {update_count} {vnp} for update.")
        return len(groups)

    #########
    # DICTS #
    #########
    @staticmethod
    def _query_missing_identifiers_model_obj(
        value_rel_map, key, values, possible_create_objs, url_restore_map
    ):
        """Update all_filters and possible_create_objs for identifiers."""
        # identifiers is unique at this time for having more than one value as a dict.
        value_filter = Q()
        # value filter
        for value in values:
            values_dict = dict(value)
            create_obj = (key, values_dict.get("nss", ""))
            url_restore_map[create_obj] = values_dict.get("url", "")
            possible_create_objs.add(create_obj)
            value_sub_filter = Q()
            for value_key, obj_rel in value_rel_map.items():
                values_value = values_dict.get(value_key)
                value_sub_filter &= Q(**{f"{obj_rel}": values_value})
            if value_sub_filter:
                value_filter |= value_sub_filter

        return value_filter

    @staticmethod
    def _query_missing_dict_model_obj(value_rel, key, values, possible_create_objs, _):
        """Update all_filters and possible_create_objs for this obj."""
        for value in values:
            possible_create_objs.add((key, value))

        filter_isnull = None in values
        filter_values = values - {None}

        if not filter_values and not filter_isnull:
            return Q()

        value_filter = (
            Q(**{f"{value_rel}__in": filter_values}) if filter_values else Q()
        )
        if filter_isnull:
            value_filter = value_filter | Q(**{f"{value_rel}__isnull": True})

        return value_filter

    def _query_missing_dict_model_add_to_query_filter_map(  # noqa: PLR0913
        self,
        key,
        values,
        field_name,
        possible_create_objs,
        query_filter_map,
        url_restore_map,
    ):
        """Add value filter to query filter map."""
        # Get the value filter
        if field_name == "identifiers":
            query_missing_method = self._query_missing_identifiers_model_obj
        else:
            query_missing_method = self._query_missing_dict_model_obj
        key_rel, value_rel = DICT_MODEL_REL_MAP[field_name]

        value_filter = query_missing_method(
            value_rel, key, values, possible_create_objs, url_restore_map
        )

        # Add value_filter to the query_filter_map
        filter_and_prefix = Q(**{key_rel: key})
        if filter_and_prefix not in query_filter_map:
            query_filter_map[filter_and_prefix] = Q()
        query_filter_map[filter_and_prefix] |= value_filter

    @staticmethod
    def _query_missing_dict_model_identifiers_restore_urls(
        field_name, possible_create_objs, url_restore_map
    ):
        """Restore urls to only the identifier create objs."""
        if field_name != "identifiers":
            return possible_create_objs
        restored_create_objs = []
        for create_obj in possible_create_objs:
            url = url_restore_map.get(create_obj)
            restored_create_objs.append((*create_obj, url))
        return restored_create_objs

    def _query_missing_dict_model(self, field_name, create_objs_key, status):
        """Find missing dict type m2m models."""
        possible_objs = self.metadata[FKS].pop(field_name, None)
        if not possible_objs:
            return 0

        # Create possible_create_objs & a query filter map and cache the urls for
        # identifiers to be created, but not queried against
        possible_create_objs = set()
        query_filter_map = {}
        url_restore_map = {}
        for key, values in possible_objs.items():
            self._query_missing_dict_model_add_to_query_filter_map(
                key,
                values,
                field_name,
                possible_create_objs,
                query_filter_map,
                url_restore_map,
            )

        # Build combined query object from the value_filter
        model = DICT_MODEL_FIELD_MODEL_MAP[field_name]
        if model == Identifier:
            for filter_and_prefix, value_filter in query_filter_map.items():
                self._query_create_metadata(
                    model,
                    possible_create_objs,
                    None,
                    value_filter,
                    status,
                    and_q_obj=filter_and_prefix,
                )
        else:
            combined_q_obj = Q()
            for filter_and_prefix, value_filter in query_filter_map.items():
                combined_q_obj |= filter_and_prefix & value_filter
            self._query_create_metadata(
                model,
                possible_create_objs,
                None,
                combined_q_obj,
                status,
            )

        # Finally run the query and get only the correct create_objs
        possible_create_objs = self._query_missing_dict_model_identifiers_restore_urls(
            field_name, possible_create_objs, url_restore_map
        )

        # Final Cleanup
        self.metadata[FK_CREATE][create_objs_key].update(possible_create_objs)
        count = len(self.metadata[FK_CREATE][create_objs_key])
        if count:
            model = DICT_MODEL_FIELD_MODEL_MAP[field_name]
            vnp = model._meta.verbose_name_plural
            vnp = vnp.title() if vnp else "Nothings"
            self.log.info(f"Prepared {count} new {vnp}.")
        status.add_complete(count)
        self.status_controller.update(status, notify=False)
        return count

    ##########
    # SIMPLE #
    ##########

    def _query_missing_simple_models(self, names, fk_data, status):
        """Find missing named models and folders."""
        # count = 0
        if not names:
            return 0
        create_fks, base_cls, field, fk_field = fk_data

        fk_cls = base_cls._meta.get_field(field).related_model

        start = 0
        proposed_names = list(names)
        create_names = set(names)
        num_proposed_names = len(proposed_names)

        vnp = fk_cls._meta.verbose_name_plural.title()
        status.subtitle = vnp
        while start < num_proposed_names:
            # Do this in batches so as not to exceed the 1k line sqlite limit
            end = start + FILTER_BATCH_SIZE
            batch_proposed_names = proposed_names[start:end]
            filter_args = {f"{fk_field}__in": batch_proposed_names}
            fk_filter = Q(**filter_args)
            create_names -= self._query_existing_mds(fk_cls, fk_filter)
            num_in_batch = len(batch_proposed_names)
            status.add_complete(num_in_batch)
            self.status_controller.update(status)
            start += FILTER_BATCH_SIZE

        if status:
            status.subtitle = ""

        if create_names:
            if fk_cls not in create_fks:
                create_fks[fk_cls] = set()
            create_fks[fk_cls].update(create_names)
            level = INFO
        else:
            level = DEBUG
        vnp = fk_cls._meta.verbose_name_plural.title()
        self.log.log(level, f"Prepared {len(create_names)} new {vnp}.")
        return len(names)

    def _query_one_simple_model(self, fk_field, status):
        """Batch query one simple model name."""
        for cls, names in DICT_MODEL_CLASS_FIELDS_MAP.items():
            if fk_field in names:
                base_cls = cls
                break
        else:
            base_cls = Comic
        fk_data = self.metadata[FK_CREATE][FKC_CREATE_FKS], base_cls, fk_field, "name"
        names = self.metadata[FKS].pop(fk_field)
        count = self._query_missing_simple_models(
            names,
            fk_data,
            status,
        )
        status.add_complete(count)
        self.status_controller.update(status, notify=False)

    ###########
    # FOLDERS #
    ###########
    def query_missing_folder_paths(
        self,
        comic_paths,
        status,
    ):
        """Find missing folder paths."""
        # Get the proposed folder_paths
        library_path = Path(self.library.path)
        proposed_folder_paths = set()
        for comic_path in comic_paths:
            for path in Path(comic_path).parents:
                if path.is_relative_to(library_path):
                    proposed_folder_paths.add(str(path))

        # get the create metadata
        create_folder_paths_dict = {}
        fk_data = (create_folder_paths_dict, Comic, PARENT_FOLDER, "path")
        self._query_missing_simple_models(
            proposed_folder_paths,
            fk_data,
            status,
        )
        create_folder_paths = create_folder_paths_dict.get(Folder, set())
        return frozenset(create_folder_paths)

    def _add_missing_folder_paths(self, comic_paths, status):
        create_folder_paths = self.query_missing_folder_paths(comic_paths, status)
        """Add missing folder_paths to create fks."""
        if FK_CREATE not in self.metadata:
            self.metadata[FK_CREATE] = {}
        if FKC_FOLDER_PATHS not in self.metadata[FK_CREATE]:
            self.metadata[FK_CREATE][FKC_FOLDER_PATHS] = set()
        self.metadata[FK_CREATE][FKC_FOLDER_PATHS] |= create_folder_paths
        if count := len(create_folder_paths):
            self.log.info(f"Prepared {count} new Folders.")

    def _get_create_fks_totals(self):
        fkc = self.metadata[FK_CREATE]
        total_fks = 0
        for data_group in chain(
            fkc[FKC_CREATE_GROUPS].values(),
            fkc[FKC_UPDATE_GROUPS].values(),
            fkc[FKC_CREATE_FKS].values(),
        ):
            total_fks += len(data_group)
        total_fks += (
            len(fkc[FKC_FOLDER_PATHS])
            + len(fkc[FKC_CONTRIBUTORS])
            + len(fkc[FKC_STORY_ARC_NUMBERS])
            + len(fkc[FKC_IDENTIFIERS])
        )
        return total_fks

    def query_all_missing_fks(self):
        """Get objects to create by querying existing objects for the proposed fks."""
        if FKS not in self.metadata:
            return
        self.metadata[FK_CREATE] = {
            FKC_CONTRIBUTORS: set(),
            FKC_STORY_ARC_NUMBERS: set(),
            FKC_IDENTIFIERS: set(),
            FKC_CREATE_GROUPS: {},
            FKC_UPDATE_GROUPS: {},
            FKC_FOLDER_PATHS: set(),
            FKC_CREATE_FKS: {},
        }
        self.log.debug(
            f"Querying existing foreign keys for comics in {self.library.path}"
        )
        status = Status(ImportStatusTypes.QUERY_MISSING_FKS)
        try:
            self.status_controller.start(status)
            for field_name, create_objs_key in _DICT_MODEL_KEY_MAP.items():
                self._query_missing_dict_model(
                    field_name,
                    create_objs_key,
                    status,
                )
            for group_class, groups in self.metadata[FKS].pop(GROUP_TREES, {}).items():
                self._query_missing_group(
                    groups,
                    group_class,
                    status,
                )

            self._add_missing_folder_paths(
                self.metadata[FKS].pop(COMIC_PATHS, ()), status
            )

            for fk_field in sorted(self.metadata[FKS].keys()):
                self._query_one_simple_model(fk_field, status)
            self.metadata.pop(FKS)
        finally:
            self.status_controller.finish(status)

        total_fks = self._get_create_fks_totals()
        status = Status(ImportStatusTypes.CREATE_FKS, 0, total_fks)
        self.status_controller.update(status, notify=False)
        self.metadata[FK_CREATE][FKC_TOTAL_FKS] = total_fks

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
    GROUP_COMPARE_FIELDS,
    GROUP_TREES,
    IDENTIFIERS_FIELD_NAME,
    IMPRINT,
    PARENT_FOLDER,
    PUBLISHER,
    SERIES,
    STORY_ARCS_METADATA_KEY,
)
from codex.librarian.importer.status import ImportStatusTypes, status_notify
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
from codex.models.paths import CustomCover
from codex.settings.settings import FILTER_BATCH_SIZE
from codex.status import Status
from codex.threads import QueuedThread

_CREATE_GROUPS = "create_groups"
_UPDATE_GROUPS = "update_groups"
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

LOG = get_logger(__name__)


class QueryForeignKeysMixin(QueuedThread):
    """Methods for querying what fks are missing."""

    @staticmethod
    def _get_query_fks_totals(fks):
        """Get the query foreign keys totals."""
        fks_total = 0
        for key, objs in fks.items():
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
    ):
        """Get create metadata by comparing proposed meatada to existing rows."""
        if status:
            vnp = fk_cls._meta.verbose_name_plural.title()
            status.subtitle = vnp
        offset = 0
        num_qs = len(q_obj.children)
        while offset < num_qs:
            # Do this in batches so as not to exceed the sqlite 1k expression tree depth limit
            # django.db.utils.OperationalError: Expression tree is too large (maximum depth 1000)
            children_chunk = q_obj.children[offset : offset + FILTER_BATCH_SIZE]
            filter_chunk = Q(*children_chunk, _connector=Q.OR)

            existing_mds = self._query_existing_mds(fk_cls, filter_chunk)
            create_mds.difference_update(existing_mds)
            if extra_update_fields := _EXTRA_UPDATE_FIELDS_MAP.get(fk_cls):
                # The mds that are in the existing_mds, but don't match the proposed mds with the extra update fields
                update_mds.update(existing_mds)
                match_with_extra_fields_mds = self._query_existing_mds(
                    fk_cls, filter_chunk, extra_update_fields
                )
                update_mds.difference_update(match_with_extra_fields_mds)

            status.complete += len(filter_chunk)
            self.status_controller.update(status)

            offset += FILTER_BATCH_SIZE

        if status:
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

    def _get_create_group_set(  # noqa: PLR0913
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

    @classmethod
    def _update_action_group(
        cls, group_cls, action_groups, group_tree, count_value: int | None
    ):
        """Update the create or update group dict with the count dict."""
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
            create_and_update_groups,
            status,
        ) = data
        if group_tree in create_group_set:
            self._update_action_group(
                group_cls,
                create_and_update_groups[_CREATE_GROUPS],
                group_tree,
                count_value,
            )
        elif group_cls in update_group_set:
            # This always updates Volume or Series
            self._update_action_group(
                group_cls,
                create_and_update_groups[_UPDATE_GROUPS],
                group_tree,
                count_value,
            )
        if status:
            status.complete = status.complete or 0
            status.complete += 1
            self.status_controller.update(status)

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

    @status_notify()
    def _query_missing_group(
        self,
        groups,
        group_cls,
        create_and_update_groups,
        status=None,
    ):
        """Get missing groups from proposed groups to create."""
        count = 0
        if not groups:
            return count

        if status:
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
            create_and_update_groups,
            status,
        )
        for group_tree, count_value in groups.items():
            self._query_group_tree(data, group_tree, count_value)

        # after counts have been tallied, prune the ones that don't need an update.
        update_groups = create_and_update_groups.get(_UPDATE_GROUPS)
        self._prune_group_updates(group_cls, update_groups)

        if status:
            status.subtitle = ""

        create_count = len(
            create_and_update_groups.get(_CREATE_GROUPS, {}).get(group_cls, {})
        )
        update_count = len(
            create_and_update_groups.get(_UPDATE_GROUPS, {}).get(group_cls, {})
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

    def _query_missing_dict_model(self, field_name, fks, create_objs, status):
        """Find missing dict type m2m models."""
        possible_objs = fks.pop(field_name, None)
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
        combined_q_obj = Q()
        for filter_and_prefix, value_filter in query_filter_map.items():
            combined_q_obj |= filter_and_prefix & value_filter

        # Finally run the query and get only the correct create_objs
        model = DICT_MODEL_FIELD_MODEL_MAP[field_name]
        self._query_create_metadata(
            model, possible_create_objs, None, combined_q_obj, status
        )
        possible_create_objs = self._query_missing_dict_model_identifiers_restore_urls(
            field_name, possible_create_objs, url_restore_map
        )

        # Final Cleanup
        create_objs.update(possible_create_objs)
        count = len(create_objs)
        if count:
            model = DICT_MODEL_FIELD_MODEL_MAP[field_name]
            vnp = model._meta.verbose_name_plural
            vnp = vnp.title() if vnp else "Nothings"
            self.log.info(f"Prepared {count} new {vnp}.")
        if status:
            status.complete = status.complete or 0
            status.complete += count
        return count

    ##########
    # SIMPLE #
    ##########

    @status_notify()
    def _query_missing_simple_models(self, names, fk_data, status=None):
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

        if status:
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
            # count += num_in_batch
            if status:
                status.complete = status.complete or 0
                status.complete += num_in_batch
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

    def _query_one_simple_model(self, fk_field, fks, create_fks, status):
        """Batch query one simple model name."""
        for cls, names in DICT_MODEL_CLASS_FIELDS_MAP.items():
            if fk_field in names:
                base_cls = cls
                break
        else:
            base_cls = Comic
        fk_data = create_fks, base_cls, fk_field, "name"
        names = fks.pop(fk_field)
        status.complete += self._query_missing_simple_models(
            names,
            fk_data,
            status=status,
        )

    ###########
    # FOLDERS #
    ###########

    @status_notify()
    def query_missing_folder_paths(
        self, comic_paths, library_path, create_folder_paths, status=None
    ):
        """Find missing folder paths."""
        # Get the proposed folder_paths
        library_path = Path(library_path)
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
            status=status,
        )
        folder_paths_set = create_folder_paths_dict.get(Folder, set())
        create_folder_paths |= folder_paths_set
        count = len(create_folder_paths)
        if count:
            self.log.info(f"Prepared {count} new Folders.")
        return count

    @staticmethod
    def _get_create_fks_totals(create_data):
        (
            create_groups,
            update_groups,
            create_folder_paths,
            create_fks,
            create_contributors,
            create_story_arc_numbers,
            create_identifiers,
        ) = create_data
        total_fks = 0
        for data_group in chain(
            create_groups.values(), update_groups.values(), create_fks.values()
        ):
            total_fks += len(data_group)
        total_fks += (
            len(create_folder_paths)
            + len(create_contributors)
            + len(create_story_arc_numbers)
            + len(create_identifiers)
        )
        return total_fks

    def query_all_missing_fks(self, library_path, fks):
        """Get objects to create by querying existing objects for the proposed fks."""
        create_contributors = set()
        create_story_arc_numbers = set()
        create_identifiers = set()
        create_groups = {}
        update_groups = {}
        create_folder_paths = set()
        create_fks = {}
        self.log.debug(f"Querying existing foreign keys for comics in {library_path}")
        fks_total = self._get_query_fks_totals(fks)
        dict_model_map = MappingProxyType(
            {
                CONTRIBUTORS_FIELD_NAME: create_contributors,
                STORY_ARCS_METADATA_KEY: create_story_arc_numbers,
                IDENTIFIERS_FIELD_NAME: create_identifiers,
            }
        )
        status = Status(ImportStatusTypes.QUERY_MISSING_FKS, 0, fks_total)
        try:
            self.status_controller.start(status)
            for field_name, create_objs in dict_model_map.items():
                self._query_missing_dict_model(
                    field_name,
                    fks,
                    create_objs,
                    status,
                )

            create_and_update_groups = {
                _CREATE_GROUPS: create_groups,
                _UPDATE_GROUPS: update_groups,
            }
            for group_class, groups in fks.pop(GROUP_TREES, {}).items():
                self._query_missing_group(
                    groups,
                    group_class,
                    create_and_update_groups,
                    status=status,
                )

            self.query_missing_folder_paths(
                fks.pop(COMIC_PATHS, ()),
                library_path,
                create_folder_paths,
                status=status,
            )

            for fk_field in sorted(fks.keys()):
                self._query_one_simple_model(fk_field, fks, create_fks, status)
        finally:
            self.status_controller.finish(status)

        create_data = (
            create_groups,
            update_groups,
            create_folder_paths,
            create_fks,
            create_contributors,
            create_story_arc_numbers,
            create_identifiers,
        )

        total_fks = self._get_create_fks_totals(create_data)
        status = Status(ImportStatusTypes.CREATE_FKS, 0, total_fks)
        self.status_controller.update(status, notify=False)
        return (*create_data, total_fks)

    @status_notify(ImportStatusTypes.QUERY_MISSING_COVERS, updates=False)
    def query_missing_custom_covers(
        self, cover_paths: frozenset, library, query_data: list, status=None
    ):
        """Identify update & create covers."""
        self.log.debug(f"Querying {len(cover_paths)} custom cover_paths")
        if status:
            status.total = len(cover_paths)

        update_covers_qs = CustomCover.objects.filter(
            library=library, path__in=cover_paths
        )
        query_data.append(update_covers_qs)
        update_cover_paths = frozenset(update_covers_qs.values_list("path", flat=True))
        update_count = len(update_cover_paths)
        update_status = Status(ImportStatusTypes.COVERS_MODIFIED, 0, update_count)
        self.status_controller.update(update_status, notify=False)

        create_cover_paths = cover_paths - update_cover_paths
        query_data.append(create_cover_paths)
        create_count = len(create_cover_paths)
        create_status = Status(ImportStatusTypes.COVERS_CREATED, 0, create_count)
        self.status_controller.update(create_status, notify=False)

        count = create_count + update_count
        if count:
            self.log.debug(
                f"Discovered {update_count} custom covers to update and {create_count} to create."
            )
            if status:
                status.add_complete(count)
        return count

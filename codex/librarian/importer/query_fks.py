"""Query the missing foreign keys for comics and creators."""
from pathlib import Path

from django.db.models import Q

from codex.librarian.importer.status import status_notify
from codex.models import (
    Comic,
    Creator,
    Folder,
    Imprint,
    Publisher,
    Series,
    Volume,
)
from codex.threads import QueuedThread

_CLASS_QUERY_FIELDS_MAP = {
    Creator: ("role__name", "person__name"),
    Folder: ("path",),
    Imprint: ("publisher__name", "name"),
    Series: ("publisher__name", "imprint__name", "name"),
    Volume: ("publisher__name", "imprint__name", "series__name", "name"),
}
_DEFAULT_QUERY_FIELDS = ("name",)
# sqlite parser breaks with more than 1000 variables in a query and django only
# fixes this in the bulk_create & bulk_update functions. So for complicated
# queries I gotta batch them myself. Filter arg count is a proxy, but it works.
_SQLITE_FILTER_ARG_MAX = 990


class QueryForeignKeysMixin(QueuedThread):
    """Methods for querying what fks are missing."""

    @staticmethod
    def _query_existing_mds(fk_cls, fk_filter):
        """Query existing metatata tables."""
        fields = _CLASS_QUERY_FIELDS_MAP.get(fk_cls, _DEFAULT_QUERY_FIELDS)
        flat = len(fields) == 1 and fk_cls != Publisher

        return set(
            fk_cls.objects.filter(fk_filter)
            .order_by("pk")
            .values_list(*fields, flat=flat)
        )

    def _query_create_metadata(self, fk_cls, create_mds, all_filter_args, status):
        """Get create metadata by comparing proposed meatada to existing rows."""
        # Do this in batches so as not to exceed the 1k line sqlite limit
        fk_filter = Q()
        filter_arg_count = 0
        all_filter_args = tuple(all_filter_args)
        if status:
            status.subtitle = fk_cls.__name__
        count = 0
        for filter_args in all_filter_args:
            fk_filter |= Q(**dict(filter_args))
            filter_arg_count += len(filter_args)
            if (
                filter_arg_count >= _SQLITE_FILTER_ARG_MAX
                or filter_args == all_filter_args[-1]
            ):
                # If too many filter args in the query or we're on the last one.
                create_mds.difference_update(
                    self._query_existing_mds(fk_cls, fk_filter)
                )
                # Reset the filter
                fk_filter = Q()
                filter_arg_count = 0

                count += 1
                status.complete += 1
                self.status_controller.update(status)

        if status:
            status.subtitle = ""

        return count

    @staticmethod
    def _add_parent_group_filter(filter_args, group_name, field_name):
        """Get the parent group filter by name."""
        key = f"{field_name}__" if field_name else ""

        key += "name"

        filter_args[key] = group_name

    def _get_create_group_set(self, groups, group_cls, create_group_set, status):
        """Create the create group set."""
        all_filter_args = set()
        for group_tree in groups:
            filter_args = {}
            self._add_parent_group_filter(filter_args, group_tree[-1], "")
            if group_cls in (Imprint, Series, Volume):
                self._add_parent_group_filter(filter_args, group_tree[0], "publisher")
            if group_cls in (Series, Volume):
                self._add_parent_group_filter(filter_args, group_tree[1], "imprint")
            if group_cls == Volume:
                self._add_parent_group_filter(filter_args, group_tree[2], "series")

            all_filter_args.add(tuple(sorted(filter_args.items())))

        candidate_groups = set(groups.keys())
        count = self._query_create_metadata(
            group_cls, candidate_groups, all_filter_args, status
        )
        create_group_set.update(candidate_groups)
        return count

    @staticmethod
    def _update_create_group(group_cls, create_groups, group_tree, count_dict):
        """Update the create group dict with the count dict."""
        if group_cls not in create_groups:
            create_groups[group_cls] = {}
        if group_tree not in create_groups[group_cls]:
            create_groups[group_cls][group_tree] = {}
        create_groups[group_cls][group_tree].update(count_dict)

    @staticmethod
    def _update_update_group(group_cls, update_groups, group_tree, count_dict):
        """Update the update group dict with the count dict."""
        if group_cls not in update_groups:
            update_groups[group_cls] = {}
        if group_tree not in update_groups[group_cls]:
            update_groups[group_cls][group_tree] = {}
        update_groups[group_cls][group_tree].update(count_dict)

    @status_notify()
    def query_missing_group(
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

        create_group_set = set()
        self._get_create_group_set(groups, group_cls, create_group_set, status)

        if status:
            status.subtitle = group_cls.__name__
        for group_tree, count_dict in groups.items():
            apply_count_dict = count_dict if count_dict else {}
            if group_tree in create_group_set:
                self._update_create_group(
                    group_cls,
                    create_and_update_groups["create_groups"],
                    group_tree,
                    apply_count_dict,
                )
            elif group_cls in (Series, Volume):
                self._update_update_group(
                    group_cls,
                    create_and_update_groups["update_groups"],
                    group_tree,
                    apply_count_dict,
                )
            count += 1
            if status:
                status.complete += 1
                self.status_controller.update(status)

        if status:
            status.subtitle = ""
        if count:
            self.log.info(f"Prepared {count} new {group_cls.__name__}s.")
        return count

    @status_notify()
    def query_missing_creators(self, creators, create_creators, status=None):
        """Find missing creator objects."""
        count = 0
        if not creators:
            return count
        # create the filter
        comparison_creators = set()
        all_filter_args = set()
        for creator_tuple in creators:
            creator_dict = dict(creator_tuple)
            role = creator_dict.get("role")
            person = creator_dict["person"]
            filter_args = {
                "person__name": person,
                "role__name": role,
            }
            all_filter_args.add(tuple(sorted(filter_args.items())))

            comparison_tuple = (role, person)
            comparison_creators.add(comparison_tuple)

        # get the create metadata
        count = self._query_create_metadata(
            Creator, comparison_creators, all_filter_args, status
        )
        create_creators.update(comparison_creators)
        if count:
            self.log.info(f"Prepared {count} new creators.")
        if status:
            status.complete += count
        return count

    @status_notify()
    def query_missing_simple_models(self, names, fk_data, status=None):
        """Find missing named models and folders."""
        count = 0
        if not names:
            return count
        create_fks, base_cls, field, fk_field = fk_data

        fk_cls = base_cls._meta.get_field(field).related_model

        start = 0
        proposed_names = list(names)
        create_names = set(names)
        num_proposed_names = len(proposed_names)

        if status:
            status.subtitle = fk_cls.__name__
        while start < num_proposed_names:
            # Do this in batches so as not to exceed the 1k line sqlite limit
            end = start + _SQLITE_FILTER_ARG_MAX
            batch_proposed_names = proposed_names[start:end]
            filter_args = {f"{fk_field}__in": batch_proposed_names}
            fk_filter = Q(**filter_args)
            create_names -= self._query_existing_mds(fk_cls, fk_filter)
            num_in_batch = len(batch_proposed_names)
            count += num_in_batch
            if status:
                status.complete += num_in_batch
                self.status_controller.update(status)
            start += _SQLITE_FILTER_ARG_MAX

        if status:
            status.subtitle = ""

        if fk_cls not in create_fks:
            create_fks[fk_cls] = set()
        create_fks[fk_cls].update(create_names)
        self.log.info(f"Prepared {count} new {field}.")
        return count

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
                if path.is_relative_to(library_path) and path != library_path:
                    proposed_folder_paths.add(str(path))

        # get the create metadata
        create_folder_paths_dict = {}
        fk_data = (create_folder_paths_dict, Comic, "parent_folder", "path")
        self.query_missing_simple_models(
            proposed_folder_paths,
            fk_data,
            status=status,
        )
        create_folder_paths.update(create_folder_paths_dict.get(Folder, set()))
        count = len(comic_paths)
        self.log.info(f"Prepared {count} new Folders.")
        return count

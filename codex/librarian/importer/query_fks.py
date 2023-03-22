"""Query the missing foreign keys for comics and credits."""
from pathlib import Path

from django.db.models import Q

from codex.librarian.importer.status import status
from codex.models import (
    Comic,
    Credit,
    Folder,
    Imprint,
    Publisher,
    Series,
    Volume,
)
from codex.threads import QueuedThread

_CLASS_QUERY_FIELDS_MAP = {
    Credit: ("role__name", "person__name"),
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
    def _query_existing_mds(fk_cls, filter):
        """Query existing metatata tables."""
        fields = _CLASS_QUERY_FIELDS_MAP.get(fk_cls, _DEFAULT_QUERY_FIELDS)
        flat = len(fields) == 1 and fk_cls != Publisher

        existing_mds = set(
            fk_cls.objects.filter(filter).order_by("pk").values_list(*fields, flat=flat)
        )
        return existing_mds

    def _query_create_metadata(self, fk_cls, create_mds, all_filter_args, status_args):
        """Get create metadata by comparing proposed meatada to existing rows."""
        # Do this in batches so as not to exceed the 1k line sqlite limit
        filter = Q()
        filter_arg_count = 0
        this_count = 0
        all_filter_args = tuple(all_filter_args)
        for num, filter_args in enumerate(all_filter_args):
            filter = filter | Q(**dict(filter_args))
            filter_arg_count += len(filter_args)
            if (
                filter_arg_count >= _SQLITE_FILTER_ARG_MAX
                or filter_args == all_filter_args[-1]
            ):
                # If too many filter args in the query or we're on the last one.
                create_mds -= self._query_existing_mds(fk_cls, filter)
                # Reset the filter
                filter = Q()
                filter_arg_count = 0

                this_count += num
                status_args.since = self.status_controller.update(
                    status_args.status,
                    status_args.count + this_count,
                    status_args.total,
                    since=status_args.since,
                    name=f"({fk_cls.__name__})",
                )

        return create_mds

    @staticmethod
    def _add_parent_group_filter(filter_args, group_name, field_name):
        """Get the parent group filter by name."""
        if field_name:
            key = f"{field_name}__"
        else:
            key = ""

        key += "name"

        filter_args[key] = group_name

    def _get_create_group_set(self, groups, group_cls, status_args):
        """Create the create group set."""
        all_filter_args = set()
        for group_tree in groups.keys():
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
        return self._query_create_metadata(
            group_cls, candidate_groups, all_filter_args, status_args
        )

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

    @status()
    def query_missing_group(
        self,
        groups,
        group_cls,
        create_groups,
        update_groups,
        status_args=None,
    ):
        """Get missing groups from proposed groups to create."""
        count = 0
        if not groups:
            return count

        create_group_set = self._get_create_group_set(groups, group_cls, status_args)

        for group_tree, count_dict in groups.items():
            if count_dict is None:
                count_dict = {}
            if group_tree in create_group_set:
                self._update_create_group(
                    group_cls, create_groups, group_tree, count_dict
                )
            elif group_cls in (Series, Volume):
                self._update_update_group(
                    group_cls, update_groups, group_tree, count_dict
                )
            count += 1
            if status_args:
                status_args.since = self.status_controller.update(
                    status_args.status,
                    status_args.count + count,
                    status_args.total,
                    since=status_args.since,
                    name=f"({group_cls.__name__})",
                )
        if count:
            self.log.info(f"Prepared {count} new {group_cls.__name__}s.")
        return count

    @status()
    def query_missing_credits(self, credits, create_credits, status_args=None):
        """Find missing credit objects."""
        count = 0
        if not credits:
            return count
        # create the filter
        comparison_credits = set()
        all_filter_args = set()
        for credit_tuple in credits:
            credit_dict = dict(credit_tuple)
            role = credit_dict.get("role")
            person = credit_dict["person"]
            filter_args = {
                "person__name": person,
                "role__name": role,
            }
            all_filter_args.add(tuple(sorted(filter_args.items())))

            comparison_tuple = (role, person)
            comparison_credits.add(comparison_tuple)

        # get the create metadata
        new_create_credits = self._query_create_metadata(
            Credit, comparison_credits, all_filter_args, status_args
        )
        create_credits.update(new_create_credits)
        count = len(new_create_credits)
        if count:
            self.log.info(f"Prepared {count} new credits.")
        return count

    @status()
    def query_missing_simple_models(
        self, names, create_fks, base_cls, field, fk_field, status_args=None
    ):
        """Find missing named models and folders."""
        count = 0
        if not names:
            return count
        fk_cls = base_cls._meta.get_field(field).related_model

        start = 0
        proposed_names = list(names)
        create_names = set(names)
        num_proposed_names = len(proposed_names)

        while start < num_proposed_names:
            # Do this in batches so as not to exceed the 1k line sqlite limit
            end = start + _SQLITE_FILTER_ARG_MAX
            batch_proposed_names = proposed_names[start:end]
            filter_args = {f"{fk_field}__in": batch_proposed_names}
            filter = Q(**filter_args)
            create_names -= self._query_existing_mds(fk_cls, filter)
            count += len(batch_proposed_names)
            if status_args:
                status_args.since = self.status_controller.update(
                    status_args.status,
                    status_args.count + count,
                    status_args.total,
                    since=status_args.since,
                    name=f"({fk_cls.__name__})",
                )
            start += _SQLITE_FILTER_ARG_MAX

        if fk_cls not in create_fks:
            create_fks[fk_cls] = set()
        create_fks[fk_cls].update(create_names)
        self.log.info(f"Prepared {count} new {field}.")
        return count

    @status()
    def query_missing_folder_paths(
        self, comic_paths, library_path, create_folder_paths, status_args=None
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
        self.query_missing_simple_models(
            proposed_folder_paths,
            create_folder_paths_dict,
            Comic,
            "parent_folder",
            "path",
            status_args=status_args,
        )
        create_folder_paths.update(create_folder_paths_dict.get(Folder, set()))
        count = len(comic_paths)
        self.log.info(f"Prepared {count} new Folders.")
        return count

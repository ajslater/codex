"""Query the missing foreign keys for comics and credits."""
from pathlib import Path

from django.db.models import Q

from codex.librarian.importer.status import ImportStatusTypes
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

    def _query_create_metadata(
        self, fk_cls, create_mds, all_filter_args, count, total, since
    ):
        """Get create metadata by comparing proposed meatada to existing rows."""
        # Do this in batches so as not to exceed the 1k line sqlite limit
        filter = Q()
        filter_arg_count = 0
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

                count += num
                since = self.status_controller.update(
                    ImportStatusTypes.QUERY_MISSING_FKS,
                    count,
                    total,
                    since=since,
                    name=fk_cls.__name__,
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

    def query_missing_group(
        self,
        _library,
        groups,
        count,
        total,
        since,
        group_cls,
        create_groups,
        update_groups,
    ):
        """Get missing groups from proposed groups to create."""
        this_count = 0

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
        create_group_set = self._query_create_metadata(
            group_cls, candidate_groups, all_filter_args, count, total, since
        )

        for group_tree, count_dict in groups.items():
            if count_dict is None:
                count_dict = {}
            if group_tree in create_group_set:
                if group_cls not in create_groups:
                    create_groups[group_cls] = {}
                if group_tree not in create_groups[group_cls]:
                    create_groups[group_cls][group_tree] = {}
                create_groups[group_cls][group_tree].update(count_dict)
            elif group_cls in (Series, Volume):
                # If Series or Volume in group tree
                if group_cls not in update_groups:
                    update_groups[group_cls] = {}
                if group_tree not in update_groups[group_cls]:
                    update_groups[group_cls][group_tree] = {}
                update_groups[group_cls][group_tree].update(count_dict)
            this_count += 1
            since = self.status_controller.update(
                ImportStatusTypes.QUERY_MISSING_FKS,
                count + this_count,
                total,
                since=since,
            )
        return this_count

    def query_missing_credits(
        self, _library, credits, count, total, since, create_credits
    ):
        """Find missing credit objects."""
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
            Credit, comparison_credits, all_filter_args, count, total, since
        )
        create_credits.update(new_create_credits)
        return len(credits)

    def query_missing_simple_models(
        self,
        _library,
        names,
        count,
        total,
        since,
        create_fks,
        base_cls,
        field,
        fk_field,
    ):
        """Find missing named models and folders."""
        # Do this in batches so as not to exceed the 1k line sqlite limit
        fk_cls = base_cls._meta.get_field(field).related_model

        start = 0
        proposed_names = list(names)
        create_names = set(names)
        num_proposed_names = len(proposed_names)
        this_count = 0

        while start < num_proposed_names:
            end = start + _SQLITE_FILTER_ARG_MAX
            batch_proposed_names = proposed_names[start:end]
            filter_args = {f"{fk_field}__in": batch_proposed_names}
            filter = Q(**filter_args)
            create_names -= self._query_existing_mds(fk_cls, filter)
            this_count += len(batch_proposed_names)
            since = self.status_controller.update(
                ImportStatusTypes.QUERY_MISSING_FKS,
                count + this_count,
                total,
                since=since,
                name=fk_cls.__name__,
            )
            start += _SQLITE_FILTER_ARG_MAX

        if fk_cls not in create_fks:
            create_fks[fk_cls] = set()
        create_fks[fk_cls].update(create_names)
        return this_count

    def query_missing_folder_paths(
        self, library, comic_paths, count, total, since, create_folder_paths
    ):
        """Find missing folder paths."""
        # Get the proposed folder_paths
        library_path = Path(library.path)
        proposed_folder_paths = set()
        for comic_path in comic_paths:
            for path in Path(comic_path).parents:
                if path.is_relative_to(library_path) and path != library_path:
                    proposed_folder_paths.add(str(path))

        # get the create metadata
        create_folder_paths_dict = {}
        self.query_missing_simple_models(
            library,
            proposed_folder_paths,
            count,
            total,
            since,
            create_folder_paths_dict,
            Comic,
            "parent_folder",
            "path",
        )
        create_folder_paths.update(create_folder_paths_dict.get(Folder, set()))
        return len(comic_paths)

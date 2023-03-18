"""Query the missing foreign keys for comics and credits."""
from pathlib import Path
from time import time

from django.db.models import Q

from codex.librarian.importer.status import ImportStatusTypes
from codex.models import (
    Comic,
    Credit,
    Folder,
    Imprint,
    LibrarianStatus,
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

    def _query_create_metadata(self, fk_cls, create_mds, all_filter_args, count, total):
        """Get create metadata by comparing proposed meatada to existing rows."""
        # Do this in batches so as not to exceed the 1k line sqlite limit
        filter = Q()
        filter_arg_count = 0
        all_filter_args = tuple(all_filter_args)
        since = time()
        ls = LibrarianStatus.objects.get(type=ImportStatusTypes.QUERY_MISSING_FKS)
        num_filter_args_batches = len(all_filter_args)
        ls_total = 0 if ls.total is None else ls.total
        ls_total += num_filter_args_batches
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

    def _get_candidate_groups(self, groups, fk_cls, count, total):
        """Get candidate groups from the metadata."""
        candidates = {}
        all_filter_args = set()
        for group_tree, count_dict in groups.items():
            filter_args = {}
            self._add_parent_group_filter(filter_args, group_tree[-1], "")
            if fk_cls in (Imprint, Series, Volume):
                self._add_parent_group_filter(filter_args, group_tree[0], "publisher")
            if fk_cls in (Series, Volume):
                self._add_parent_group_filter(filter_args, group_tree[1], "imprint")
            if fk_cls == Volume:
                self._add_parent_group_filter(filter_args, group_tree[2], "series")

            all_filter_args.add(tuple(sorted(filter_args.items())))
            candidates[group_tree] = count_dict

        # get the create metadata
        candidate_groups = set(candidates.keys())
        create_group_set = self._query_create_metadata(
            fk_cls, candidate_groups, all_filter_args, count, total
        )
        return candidates, create_group_set

    def _update_create_and_update_groups(
        self,
        candidates,
        create_group_set,
        create_groups,
        update_groups,
        fk_cls,
        count,
        total,
        since,
    ):
        """Take the candidates and update the create and update groups."""
        this_count = 0
        for group_tree, count_dict in candidates.items():
            if count_dict:
                if group_tree in create_group_set:
                    if group_tree not in create_groups:
                        create_groups[group_tree] = {}
                    create_groups[group_tree].update(count_dict)
                elif fk_cls in (Series, Volume):
                    # If Series or Volume in group tree
                    if group_tree not in update_groups:
                        update_groups[group_tree] = {}
                    update_groups[group_tree].update(count_dict)
                this_count += len(count_dict)
            else:
                this_count = 0
            since = self.status_controller.update(
                ImportStatusTypes.QUERY_MISSING_FKS,
                count + this_count,
                total,
                since=since,
            )
        return this_count

    def query_missing_group_type(
        self, _library, groups, count, total, fk_cls, create_groups, update_groups
    ):
        """Get missing groups from proposed groups to create."""
        since = time()
        # Append the count metadata to the create_groups
        candidates, create_group_set = self._get_candidate_groups(
            groups, fk_cls, count, total
        )
        return self._update_create_and_update_groups(
            candidates,
            create_group_set,
            create_groups,
            update_groups,
            fk_cls,
            count,
            total,
            since,
        )

    def query_missing_credits(self, _library, credits, count, total, create_credits):
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
            Credit, comparison_credits, all_filter_args, count, total
        )
        create_credits.update(new_create_credits)
        return len(credits)

    def query_missing_simple_models(
        self, _library, names, count, total, create_fks, base_cls, field, fk_field
    ):
        """Find missing named models and folders."""
        # Do this in batches so as not to exceed the 1k line sqlite limit
        fk_cls = base_cls._meta.get_field(field).related_model

        offset = 0
        proposed_names = list(names)
        create_names = set(names)
        num_proposed_names = len(proposed_names)
        num = 0
        since = time()

        while offset < num_proposed_names:
            end = offset + _SQLITE_FILTER_ARG_MAX
            batch_proposed_names = proposed_names[offset:end]
            filter_args = {f"{fk_field}__in": batch_proposed_names}
            filter = Q(**filter_args)
            create_names -= self._query_existing_mds(fk_cls, filter)
            num += len(batch_proposed_names)
            count += num
            since = self.status_controller.update(
                ImportStatusTypes.QUERY_MISSING_FKS,
                count,
                total,
                since=since,
                name=fk_cls.__name__,
            )
            offset += _SQLITE_FILTER_ARG_MAX

        if fk_cls not in create_fks:
            create_fks[fk_cls] = {}
        create_fks[fk_cls].update(create_names)
        return len(names)

    def query_missing_folder_paths(
        self, library, comic_paths, count, total, create_folder_paths
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
        count = self.query_missing_simple_models(
            library,
            proposed_folder_paths,
            count,
            total,
            create_folder_paths_dict,
            Comic,
            "parent_folder",
            "path",
        )
        create_folder_paths.update(create_folder_paths_dict.get(Folder, set()))
        return count

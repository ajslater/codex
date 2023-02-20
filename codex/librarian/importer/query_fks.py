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

_CREDIT_FK_NAMES = ("role", "person")
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

    def _query_create_metadata(self, fk_cls, create_mds, all_filter_args):
        """Get create metadata by comparing proposed meatada to existing rows."""
        # Do this in batches so as not to exceed the 1k line sqlite limit
        filter = Q()
        filter_arg_count = 0
        all_filter_args = tuple(all_filter_args)
        since = time()
        ls = LibrarianStatus.objects.get(type=ImportStatusTypes.QUERY_MISSING_FKS)
        ls_complete = ls.complete
        num_filter_args_batches = len(all_filter_args)
        ls_total = ls.total
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

                since = self.status_controller.update(
                    ImportStatusTypes.QUERY_MISSING_FKS,
                    ls_complete + num,
                    ls_total,
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

    def _query_missing_group_type(self, fk_cls, groups):
        """Get missing groups from proposed groups to create."""
        # create the filters
        candidates = {}
        all_filter_args = set()
        for group_tree, count in groups.items():
            filter_args = {}
            self._add_parent_group_filter(filter_args, group_tree[-1], "")
            if fk_cls in (Imprint, Series, Volume):
                self._add_parent_group_filter(filter_args, group_tree[0], "publisher")
            if fk_cls in (Series, Volume):
                self._add_parent_group_filter(filter_args, group_tree[1], "imprint")
            if fk_cls == Volume:
                self._add_parent_group_filter(filter_args, group_tree[2], "series")

            all_filter_args.add(tuple(sorted(filter_args.items())))
            candidates[group_tree] = count

        # get the create metadata
        candidate_groups = set(candidates.keys())
        create_group_set = self._query_create_metadata(
            fk_cls, candidate_groups, all_filter_args
        )

        # Append the count metadata to the create_groups
        create_groups = {}
        update_groups = {}
        for group_tree, count_dict in candidates.items():
            if group_tree in create_group_set:
                create_groups[group_tree] = count_dict
            elif fk_cls in (Series, Volume):
                # If Series or Volume in group tree
                update_groups[group_tree] = count_dict
        return create_groups, update_groups

    def _query_missing_groups(self, group_trees_md):
        """Get missing groups from proposed groups to create."""
        all_create_groups = {}
        all_update_groups = {}
        count = 0
        for group_class, groups in group_trees_md.items():
            create_groups, update_groups = self._query_missing_group_type(
                group_class, groups
            )
            all_create_groups[group_class] = create_groups
            if update_groups:
                all_update_groups[group_class] = update_groups
            count += len(create_groups)
        return all_create_groups, all_update_groups, count

    def _query_missing_credits(self, credits):
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
        return self._query_create_metadata(Credit, comparison_credits, all_filter_args)

    def _query_missing_simple_models(self, base_cls, field, fk_field, names):
        """Find missing named models and folders."""
        # Do this in batches so as not to exceed the 1k line sqlite limit
        fk_cls = base_cls._meta.get_field(field).related_model

        offset = 0
        proposed_names = list(names)
        create_names = set(names)
        num_proposed_names = len(proposed_names)
        num = 0
        since = time()

        # Init status update.
        ls = LibrarianStatus.objects.get(type=ImportStatusTypes.QUERY_MISSING_FKS)
        ls_complete = ls.complete
        ls_total = ls.total

        while offset < num_proposed_names:
            end = offset + _SQLITE_FILTER_ARG_MAX
            batch_proposed_names = proposed_names[offset:end]
            filter_args = {f"{fk_field}__in": batch_proposed_names}
            filter = Q(**filter_args)
            create_names -= self._query_existing_mds(fk_cls, filter)
            num += len(batch_proposed_names)
            since = self.status_controller.update(
                ImportStatusTypes.QUERY_MISSING_FKS,
                ls_complete + num,
                ls_total,
                since=since,
                name=fk_cls.__name__,
            )
            offset += _SQLITE_FILTER_ARG_MAX

        return fk_cls, create_names

    def query_missing_folder_paths(self, library_path, comic_paths):
        """Find missing folder paths."""
        # Get the proposed folder_paths
        library_path = Path(library_path)
        proposed_folder_paths = set()
        for comic_path in comic_paths:
            for path in Path(comic_path).parents:
                if path.is_relative_to(library_path) and path != library_path:
                    proposed_folder_paths.add(str(path))

        # get the create metadata
        _, create_folder_paths = self._query_missing_simple_models(
            Comic, "parent_folder", "path", proposed_folder_paths
        )

        return create_folder_paths

    def _init_status(self, fks):
        """Initialize Status update."""
        ls_total = 0
        for key, objs in fks.items():
            if key == "group_trees":
                for trees in objs.values():
                    ls_total += len(trees)
            else:
                ls_total += len(objs)

        self.status_controller.start(ImportStatusTypes.QUERY_MISSING_FKS, ls_total)

    def query_all_missing_fks(self, library_path, fks):
        """Get objects to create by querying existing objects for the proposed fks."""
        try:
            self.log.debug(
                f"Querying existing foreign keys for comics in {library_path}"
            )
            self._init_status(fks)

            create_credits = set()
            if "credits" in fks:
                credits = fks.pop("credits")
                create_credits |= self._query_missing_credits(credits)
                self.log.info(f"Prepared {len(create_credits)} new credits.")

            if "group_trees" in fks:
                group_trees = fks.pop("group_trees")
                (
                    create_groups,
                    update_groups,
                    create_group_count,
                ) = self._query_missing_groups(group_trees)
                self.log.info(f"Prepared {create_group_count} new groups.")
            else:
                create_groups = {}
                update_groups = {}

            create_folder_paths = set()
            if "comic_paths" in fks:
                create_folder_paths |= self.query_missing_folder_paths(
                    library_path, fks.pop("comic_paths")
                )
                self.log.info(f"Prepared {len(create_folder_paths)} new folders.")

            create_fks = {}
            for field in fks.keys():
                names = fks.get(field)
                if field in _CREDIT_FK_NAMES:
                    base_cls = Credit
                else:
                    base_cls = Comic
                model, names = self._query_missing_simple_models(
                    base_cls, field, "name", names
                )
                create_fks[model] = names
                if num_names := len(names):
                    self.log.info(f"Prepared {num_names} new {field}.")

            return (
                create_fks,
                create_groups,
                update_groups,
                create_folder_paths,
                create_credits,
            )
        finally:
            self.status_controller.finish(ImportStatusTypes.QUERY_MISSING_FKS)

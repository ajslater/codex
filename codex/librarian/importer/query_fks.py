"""Query the missing foreign keys for comics and creators."""
from collections.abc import Iterable
from pathlib import Path

from django.db.models import Q

from codex.librarian.importer.status import ImportStatusTypes, status_notify
from codex.models import (
    Comic,
    Creator,
    Folder,
    Imprint,
    Publisher,
    Series,
    StoryArcNumber,
    Volume,
)
from codex.status import Status
from codex.threads import QueuedThread

_CLASS_QUERY_FIELDS_MAP = {
    Creator: ("role__name", "person__name"),
    StoryArcNumber: ("story_arc__name", "number"),
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
_CREATOR_FK_NAMES = ("role", "person")


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

    def _query_create_metadata(
        self,
        fk_cls,
        create_mds,
        all_filter_args: Iterable[tuple[tuple[str, str], ...]],
        status,
    ):
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
    def _add_parent_group_filter(
        filter_args: dict[str, str], group_name: str, field_name: str
    ):
        """Get the parent group filter by name."""
        key = f"{field_name}__" if field_name else ""

        key += "name"

        filter_args[key] = group_name

    def _get_create_group_set(self, groups, group_cls, create_group_set, status):
        """Create the create group set."""
        all_filter_args: set[tuple[tuple[str, str], ...]] = set()
        for group_tree in groups:
            filter_args: dict[str, str] = {}
            self._add_parent_group_filter(filter_args, group_tree[-1], "")
            if group_cls in (Imprint, Series, Volume):
                self._add_parent_group_filter(filter_args, group_tree[0], "publisher")
            if group_cls in (Series, Volume):
                self._add_parent_group_filter(filter_args, group_tree[1], "imprint")
            if group_cls == Volume:
                self._add_parent_group_filter(filter_args, group_tree[2], "series")

            serialized_filter_args: tuple[tuple[str, str], ...] = tuple(
                sorted(filter_args.items())
            )
            all_filter_args.add(serialized_filter_args)

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

    def _query_group_tree(self, data, group_tree, count_dict):
        """Query missing groups for one group tree depth."""
        (
            create_group_set,
            group_cls,
            create_and_update_groups,
            status,
        ) = data
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
        if status:
            status.complete = status.complete or 0
            status.complete += 1
            self.status_controller.update(status)

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

        create_group_set = set()
        self._get_create_group_set(groups, group_cls, create_group_set, status)

        if status:
            status.subtitle = group_cls.__name__

        data = (create_group_set, group_cls, create_and_update_groups, status)
        for group_tree, count_dict in groups.items():
            self._query_group_tree(data, group_tree, count_dict)

        if status:
            status.subtitle = ""
        count = len(groups)
        if count:
            self.log.info(f"Prepared {count} new {group_cls.__name__}s.")
        return count

    @staticmethod
    def _get_query_filter_creators(creator_tuple):
        """Get serialized comparison object data for Creators."""
        creator_dict = dict(creator_tuple)
        role = creator_dict.get("role")
        person = creator_dict["person"]
        filter_args = {
            "person__name": person,
            "role__name": role,
        }
        comparison_tuple = (role, person)
        return filter_args, comparison_tuple

    @staticmethod
    def _get_query_filter_story_arc_numbers(story_arc_number_tuple):
        """Get serialized comparison object data for StoryArcNumbers."""
        story_arc, number = story_arc_number_tuple
        filter_args = {
            "story_arc__name": story_arc,
            "number": number,
        }
        comparison_tuple = (story_arc, number)
        return filter_args, comparison_tuple

    def _query_missing_dict_model(self, possible_objs, model_data, create_objs, status):
        """Find missing dict type m2m models with a supplied filter method."""
        count = 0
        if not possible_objs:
            return count
        # create the filter
        (get_query_filter_method, model) = model_data
        comparison_objs = set()
        all_filter_args = set()
        for obj_tuple in possible_objs:
            filter_args, comparison_tuple = get_query_filter_method(obj_tuple)
            all_filter_args.add(tuple(sorted(filter_args.items())))
            comparison_objs.add(comparison_tuple)

        # get the obj metadata
        count = self._query_create_metadata(
            model, comparison_objs, all_filter_args, status
        )
        create_objs.update(comparison_objs)
        if count:
            self.log.info(f"Prepared {count} new {model.__class__.__name__}s.")
        if status:
            status.complete = status.complete or 0
            status.complete += count
        return count

    @status_notify()
    def _query_missing_creators(self, creators, create_creators, status=None):
        """Find missing creator objects."""
        model_data = (self._get_query_filter_creators, Creator)
        return self._query_missing_dict_model(
            creators,
            model_data,
            create_creators,
            status,
        )

    @status_notify()
    def _query_missing_story_arc_numbers(
        self, story_arc_numbers, create_story_arc_numbers, status=None
    ):
        """Find missing story arc number objects."""
        model_data = (
            self._get_query_filter_story_arc_numbers,
            StoryArcNumber,
        )
        return self._query_missing_dict_model(
            story_arc_numbers,
            model_data,
            create_story_arc_numbers,
            status,
        )

    @status_notify()
    def _query_missing_simple_models(self, names, fk_data, status=None):
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
                status.complete = status.complete or 0
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
        self._query_missing_simple_models(
            proposed_folder_paths,
            fk_data,
            status=status,
        )
        create_folder_paths.update(create_folder_paths_dict.get(Folder, set()))
        count = len(comic_paths)
        self.log.info(f"Prepared {count} new Folders.")
        return count

    @staticmethod
    def _get_query_fks_totals(fks):
        """Get the query foreign keys totals."""
        fks_total = 0
        for key, objs in fks.items():
            if key == "group_trees":
                for groups in objs.values():
                    fks_total += len(groups)
            else:
                fks_total += len(objs)
        return fks_total

    def _query_one_simple_model(self, fk_field, names, create_fks, status):
        """Batch query one simple model name."""
        if fk_field in _CREATOR_FK_NAMES:
            base_cls = Creator
        elif fk_field == "story_arc":
            base_cls = StoryArcNumber
        else:
            base_cls = Comic
        fk_data = create_fks, base_cls, fk_field, "name"
        status.complete += self._query_missing_simple_models(
            names,
            fk_data,
            status=status,
        )

    def query_all_missing_fks(self, library_path, fks):
        """Get objects to create by querying existing objects for the proposed fks."""
        create_creators = set()
        create_story_arc_numbers = set()
        create_groups = {}
        update_groups = {}
        create_folder_paths = set()
        create_fks = {}
        self.log.debug(f"Querying existing foreign keys for comics in {library_path}")
        fks_total = self._get_query_fks_totals(fks)
        status = Status(ImportStatusTypes.QUERY_MISSING_FKS, 0, fks_total)
        try:
            self.status_controller.start(status)

            self._query_missing_creators(
                fks.pop("creators", {}),
                create_creators,
                status=status,
            )

            self._query_missing_story_arc_numbers(
                fks.pop("story_arc_numbers", {}),
                create_story_arc_numbers,
                status=status,
            )

            create_and_update_groups = {
                "create_groups": create_groups,
                "update_groups": update_groups,
            }
            for group_class, groups in fks.pop("group_trees", {}).items():
                self._query_missing_group(
                    groups,
                    group_class,
                    create_and_update_groups,
                    status=status,
                )

            self.query_missing_folder_paths(
                fks.pop("comic_paths", ()),
                library_path,
                create_folder_paths,
                status=status,
            )

            for fk_field in sorted(fks.keys()):
                self._query_one_simple_model(
                    fk_field, fks.pop(fk_field), create_fks, status
                )
        finally:
            self.status_controller.finish(status)

        return (
            create_groups,
            update_groups,
            create_folder_paths,
            create_fks,
            create_creators,
            create_story_arc_numbers,
        )

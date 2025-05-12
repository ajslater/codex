"""Query the missing group foreign keys."""

from django.db.models import Q

from codex.librarian.importer.const import (
    COUNT_FIELDS,
    FK_CREATE,
    FKC_CREATE_GROUPS,
    FKC_UPDATE_GROUPS,
    GROUP_COMPARE_FIELDS,
    IMPRINT,
    PUBLISHER,
    SERIES,
)
from codex.librarian.importer.query_fks.query import QueryForeignKeysQueryImporter
from codex.models import (
    Imprint,
    Series,
    Volume,
)
from codex.models.groups import BrowserGroupModel
from codex.settings.settings import FILTER_BATCH_SIZE

_HAS_IMPRINT_LINKS = frozenset({Series, Volume})
_HAS_PUBLISHER_LINKS = frozenset({Imprint} | _HAS_IMPRINT_LINKS)


class QueryForeignKeysGroupsImporter(QueryForeignKeysQueryImporter):
    """Methods for querying what fks are missing."""

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
            if group_cls in _HAS_PUBLISHER_LINKS:
                self._add_parent_group_filter(filter_args, group_tree[0], PUBLISHER)
            if group_cls in _HAS_IMPRINT_LINKS:
                self._add_parent_group_filter(filter_args, group_tree[1], IMPRINT)
            if group_cls == Volume:
                self._add_parent_group_filter(filter_args, group_tree[2], SERIES)

            all_filters |= Q(**filter_args)

        candidate_groups = set(groups.keys())
        update_groups = set()
        count = self.query_create_metadata(
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
    def _prune_group_updates_get_filter(
        group_cls: type[BrowserGroupModel],
        update_group_trees: dict[tuple[str, ...], int | None],
    ):
        """Construct the big filter for groups."""
        compare_fields = GROUP_COMPARE_FIELDS[group_cls]
        count_field_name = COUNT_FIELDS[group_cls]

        group_filter = Q()
        for group_tree, count_value in update_group_trees.items():
            compare_filter: dict[str, str | int | None] = dict(
                zip(compare_fields, group_tree, strict=False)
            )
            if count_field_name:
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

    def query_missing_group(
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
            if create_count:
                self.log.info(f"Prepared {create_count} {vnp} for creation.")
            if update_count:
                self.log.info(f"Prepared {update_count} {vnp} for update.")
        return len(groups)

"""Aggregate Browser Group Trees."""

from types import MappingProxyType

from codex.librarian.importer.aggregate.const import COMIC_FK_FIELD_NAMES
from codex.librarian.importer.const import (
    FK_LINK,
    GROUP_MODEL_COUNT_FIELDS,
    QUERY_MODELS,
)
from codex.librarian.importer.extract import ExtractMetadataImporter
from codex.models.groups import BrowserGroupModel
from codex.util import max_none

_BROWSER_GROUPS_MAP = MappingProxyType(
    {
        cls: (cls.__name__.lower(), cls.name.field)  # pyright: ignore[reportAttributeAccessIssue]
        for cls in GROUP_MODEL_COUNT_FIELDS
    }
)


class AggregateForeignKeyMetadataImporter(ExtractMetadataImporter):
    """Aggregate Browser Group Trees."""

    @staticmethod
    def _set_group_tree_group(
        attrs: tuple,
        md: dict,
        group_cls: type[BrowserGroupModel],
        groups_md: dict,
        group_tree: list,
    ):
        group_field_name, field = attrs
        group = md.pop(group_field_name, {})
        group_name = group.get("name", group_cls.DEFAULT_NAME)
        group_name = field.get_prep_value(group_name)
        if (count_key := GROUP_MODEL_COUNT_FIELDS.get(group_cls)) and (
            count := group.get(count_key)
        ):
            groups_md[count_key] = count
        group_tree.append(group_name)

    def _set_group_tree_max_group_count(  # noqa: PLR0913
        self,
        path,
        group_tree,
        group_md,
        group_class,
        index: int,
        count_key: str | None = None,
    ):
        """Assign the maximum group count number."""
        group_list = group_tree[0:index]
        if count_key:
            try:
                count = max_none(
                    self.metadata[QUERY_MODELS].get(group_class, {}).get(group_list),
                    group_md.get(count_key),
                )
            except Exception:
                count = None
        else:
            count = None

        group = {group_list: count}
        # Update is fine because count max merge happens above
        if group_class not in self.metadata[QUERY_MODELS]:
            self.metadata[QUERY_MODELS][group_class] = {}
        self.metadata[QUERY_MODELS][group_class].update(group)
        field_name = group_class.__name__.lower()
        self.metadata[FK_LINK][path][field_name] = group_list[-1]

    def get_group_tree(self, md, path):
        """Create the group tree to counts map for a single comic."""
        # Create group tree
        group_tree = []
        groups_md = {}
        for group_class, attrs in _BROWSER_GROUPS_MAP.items():
            self._set_group_tree_group(
                attrs,
                md,
                group_class,
                groups_md,
                group_tree,
            )

        group_tree = tuple(group_tree)

        # Aggregate into fks
        # query and create from group_trees
        for index, (group_class, count_field_name) in enumerate(
            GROUP_MODEL_COUNT_FIELDS.items(), start=1
        ):
            self._set_group_tree_max_group_count(
                path, group_tree, groups_md, group_class, index, count_field_name
            )

    def get_fk_metadata(self, md, path):
        """Aggregate Simple Foreign Keys."""
        for field_name, related_field in COMIC_FK_FIELD_NAMES.items():
            value = md.pop(field_name, None)
            if value is None:
                continue
            value = related_field.get_prep_value(value)

            model = related_field.model
            if model not in self.metadata[QUERY_MODELS]:
                self.metadata[QUERY_MODELS][model] = set()
            self.metadata[QUERY_MODELS][model].add(value)
            self.metadata[FK_LINK][path][field_name] = value

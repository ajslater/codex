"""Browser breadcrumbs calculations."""

from types import MappingProxyType
from typing import TYPE_CHECKING

from codex.views.browser.browser_annotations import BrowserAnnotationsView
from codex.views.const import GROUP_NAME_MAP

if TYPE_CHECKING:
    from codex.models.paths import Folder


class BrowserBreadcrumbsView(BrowserAnnotationsView):
    """Browser breadcrumbs calculations."""

    def _is_breadcrumbs_child_folder(self, is_child, group, up_group, up_pks) -> bool:
        """Is this page a child of the folder breadcrumbs."""
        if group != up_group or not self.group_instance:  # type: ignore
            return is_child
        parent_folder: Folder | None = self.group_instance.parent_folder  # type: ignore
        parent_pk = parent_folder.pk if parent_folder else 0
        return parent_pk in up_pks or (not up_pks and not parent_pk)

    def _is_breadcrumbs_child_groups(self, is_child, group, up_group, up_pks):
        """Is this page a child of the group breadcrumbs."""
        show = self.params["show"]
        test_parent = False
        parent_group = None
        for show_group, enabled in reversed(show.items()):
            if not test_parent:
                if show_group == group:
                    test_parent = True
                continue
            if not enabled:
                continue
            group_name = GROUP_NAME_MAP[show_group]
            parent_group = getattr(self.group_instance, group_name, None)  # type: ignore
            is_child = bool(parent_group) and (parent_group.pk in up_pks)
            break
        if up_group == "r" and not parent_group:
            is_child = True
        return is_child

    def _is_breadcrumbs_child(self, breadcrumbs) -> bool:
        """Is the current route a child of the stored breadcrumbs."""
        is_child = False
        if not breadcrumbs:
            return is_child
        group = self.kwargs["group"]
        pks = self.kwargs["pks"]
        up_route = breadcrumbs[-1]
        up_group = up_route["group"]
        up_pks = up_route["pks"]
        if group == self.STORY_ARC_GROUP:
            is_child = group == up_group and pks
        elif group == self.FOLDER_GROUP:
            is_child = self._is_breadcrumbs_child_folder(
                is_child, group, up_group, up_pks
            )
        else:
            is_child = self._is_breadcrumbs_child_groups(
                is_child, group, up_group, up_pks
            )

        return is_child

    def _create_breadcrumbs_story_arc(self):
        """Create the only story_arc parent."""
        return [
            {
                "group": self.STORY_ARC_GROUP,
                "pks": (),
                "page": 1,
                "name": "",
            }
        ]

    def _create_breadcrumbs_folder(self):
        """Create folder parents."""
        breadcrumbs = []
        folder: Folder | None = self.group_instance  # type: ignore
        while folder:
            folder = folder.parent_folder  # type: ignore
            pks = (folder.pk,) if folder else ()
            name = folder.name if folder else ""
            parent_route = {
                "group": self.FOLDER_GROUP,
                "pks": pks,
                "page": 1,
                "name": name,
            }
            breadcrumbs = [parent_route, *breadcrumbs]
        return breadcrumbs

    def _create_breadcrumbs_group(self):
        """Create browse group parents."""
        breadcrumbs = [{"group": self.ROOT_GROUP, "pks": (), "page": 1, "name": ""}]
        show = self.params["show"]
        for show_group, enabled in show.items():
            if not enabled or show_group not in self.valid_nav_groups:  # type: ignore
                continue
            attr = GROUP_NAME_MAP[show_group]  # + "_id"
            parent_group = getattr(self.group_instance, attr, None)  # type: ignore
            if parent_group:
                pks = (parent_group.pk,)
                name = parent_group.name
                parent_group_route = {
                    "group": show_group,
                    "pks": pks,
                    "page": 1,
                    "name": name,
                }
                breadcrumbs += [parent_group_route]
        return breadcrumbs

    def _create_breadcrumbs(self):
        """Create breadcrumbs from scratch."""
        pks = self.kwargs["pks"]
        if not pks:
            return []
        group = self.kwargs["group"]
        if group == self.STORY_ARC_GROUP:
            breadcrumbs = self._create_breadcrumbs_story_arc()
        elif group == self.FOLDER_GROUP:
            breadcrumbs = self._create_breadcrumbs_folder()
        else:
            breadcrumbs = self._create_breadcrumbs_group()
        return breadcrumbs

    def _is_breadcrumbs_identical(self, breadcrumbs):
        if not breadcrumbs:
            return False

        up_route = breadcrumbs[-1]
        if not up_route:
            return False

        group = self.kwargs["group"]
        if up_route["group"] != group:
            return False

        pks = self.kwargs["pks"]
        if set(up_route["pks"]) != set(pks):
            return False

        return True

    def get_parent_breadcrumbs(
        self,
    ) -> tuple[dict[str, str | tuple[int, ...] | int], ...]:
        """Get the breadcrumbs."""
        breadcrumbs: list[dict[str, str | tuple[int, ...] | int]] = list(
            self.get_from_session("breadcrumbs")
        )

        if not self._is_breadcrumbs_identical(breadcrumbs):
            if not self._is_breadcrumbs_child(breadcrumbs):
                breadcrumbs = self._create_breadcrumbs()

            # Add current route to crumbs
            group = self.kwargs["group"]
            pks = self.kwargs["pks"]
            name = self.group_instance.name if self.group_instance else ""  # type: ignore
            page = self.kwargs["page"]
            route = {"group": group, "pks": pks, "page": page, "name": name}
            breadcrumbs += [route]

            # Save params
            params = dict(self.params)
            params["breadcrumbs"] = breadcrumbs
            self.params = MappingProxyType(params)

        parent_breadcrumbs = breadcrumbs[:-1] if breadcrumbs else ()

        return tuple(parent_breadcrumbs)

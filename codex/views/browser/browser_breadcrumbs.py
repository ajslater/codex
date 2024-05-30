"""Browser breadcrumbs calculations."""

from types import MappingProxyType

from codex.logger.logging import get_logger
from codex.views.browser.browser_annotations import BrowserAnnotationsView
from codex.views.const import FOLDER_GROUP, GROUP_NAME_MAP, ROOT_GROUP, STORY_ARC_GROUP
from codex.views.util import Route

LOG = get_logger(__name__)

_GROUP_ORDER = "rpisv"  # TODO move to const


class BrowserBreadcrumbsView(BrowserAnnotationsView):
    """Browser breadcrumbs calculations."""

    def _init_breadcrumbs(self, valid_groups):
        """Load breadcrumbs and determine if they should be searched for a graft."""
        breadcrumbs: list[Route] = list(self.params.get("breadcrumbs", []))
        old_breadcrumbs = [Route(**crumb) for crumb in breadcrumbs]
        changed = bool(old_breadcrumbs) and old_breadcrumbs[-1].group in valid_groups
        if changed:
            old_breadcrumbs = []
        return old_breadcrumbs, changed

    def _breadcrumbs_save(self, breadcrumbs):
        """Save the breadcrumbs to params."""
        params = dict(self.params)
        params["breadcrumbs"] = tuple(crumb.dict() for crumb in breadcrumbs)
        self.params = MappingProxyType(params)

    def _breadcrumbs_graft_or_create_story_arc(self) -> tuple[tuple[Route, ...], bool]:
        """Graft or create story_arc breadcrumbs."""
        old_breadcrumbs, changed = self._init_breadcrumbs(STORY_ARC_GROUP)

        pks = self.kwargs["pks"]
        page = self.kwargs["page"]
        gi = self.group_instance  # type: ignore
        name = gi.name if gi else ""
        new_crumb = Route(STORY_ARC_GROUP, pks, page, name)

        if old_breadcrumbs and old_breadcrumbs[-1] & new_crumb:
            # Graft. Hurray
            breadcrumbs = old_breadcrumbs
        else:
            # Create
            new_breadcrumbs = [new_crumb]
            if new_crumb.pks and 0 not in new_crumb.pks:
                # Add head.
                new_breadcrumbs = [Route(STORY_ARC_GROUP, ()), *new_breadcrumbs]
            changed = True
            breadcrumbs = new_breadcrumbs

        return tuple(breadcrumbs), changed

    @staticmethod
    def _breadcrumb_find_branch(reverse_breadcrumbs, crumb) -> list[Route] | None:
        """Find a graftable breadcrumb branch."""
        for index, breadcrumb in enumerate(reverse_breadcrumbs):
            if breadcrumb & crumb:
                return list(reversed(reverse_breadcrumbs[index:]))
        return None

    def _breadcrumbs_graft_or_create_folder(self) -> tuple[tuple[Route, ...], bool]:
        """Graft or create folder breadcrumbs."""
        old_breadcrumbs, changed = self._init_breadcrumbs(FOLDER_GROUP)

        reversed_breadcrumbs = list(reversed(old_breadcrumbs))

        folder = self.group_instance  # type: ignore
        name = folder.name if folder else "All"
        new_crumb = Route(FOLDER_GROUP, self.kwargs["pks"], self.kwargs["page"], name)
        new_breadcrumbs = []

        while True:
            branch = self._breadcrumb_find_branch(reversed_breadcrumbs, new_crumb)
            if branch and not branch[0].pks:
                # Branch must have the top as a head.
                # Graft. Hurray.
                new_breadcrumbs = branch + new_breadcrumbs
                break

            # Add head
            new_breadcrumbs = [new_crumb, *new_breadcrumbs]
            changed = True
            if not new_crumb.pks:
                break

            # parent next
            folder = folder.parent_folder
            if folder:
                new_crumb = Route(FOLDER_GROUP, (folder.pk,), 1, name=folder.name)
            else:
                new_crumb = Route(FOLDER_GROUP, (), 1, name="All")

        breadcrumbs = new_breadcrumbs

        return tuple(breadcrumbs), changed

    def _breadcrumbs_graft_or_create_group_one(
        self, group, old_breadcrumbs, new_breadcrumbs, changed
    ) -> tuple[bool, bool]:
        """Graft or create one browse group breadcrumb."""
        gi = self.group_instance  # type: ignore
        if not gi:
            new_crumb = Route(ROOT_GROUP, ())
        if group == self.kwargs["group"]:
            # create self crumb
            name = gi.name if gi else "All"
            pks = self.kwargs["pks"]
            page = self.kwargs["page"]
        else:
            new_crumb = None
            page = 1
            if (attr := GROUP_NAME_MAP.get(group)) and (
                parent_group := getattr(gi, attr, None)
            ):
                pks = (parent_group.pk,)
                name = parent_group.name
            else:
                pks = ()
                name = "All"

        new_crumb = Route(group, pks, page, name)

        if old_breadcrumbs and (
            (new_crumb == old_breadcrumbs[-1])
            or (changed and (new_crumb & old_breadcrumbs[-1]))
            and not old_breadcrumbs[0].pks
        ):
            # Graft. Hurray
            new_breadcrumbs[0:0] = old_breadcrumbs
            done = True
        else:
            # Insert the new node
            new_breadcrumbs.insert(0, new_crumb)
            changed = True
            done = False
        return done, changed

    def _breadcrumbs_graft_or_create_group(self) -> tuple[tuple[Route, ...], bool]:
        """Graft or create browse group breadcrumbs."""
        old_breadcrumbs, changed = self._init_breadcrumbs(_GROUP_ORDER)

        vng = self.valid_nav_groups  # type: ignore
        test_groups = tuple(reversed(vng[:-1]))
        new_breadcrumbs = []
        level = done = False
        browser_group_index = _GROUP_ORDER.index(self.kwargs["group"])

        for group in test_groups:
            try:
                level = level or _GROUP_ORDER.index(group) <= browser_group_index
                if level:
                    done, changed = self._breadcrumbs_graft_or_create_group_one(
                        group, old_breadcrumbs, new_breadcrumbs, changed
                    )
                if old_breadcrumbs and _GROUP_ORDER.index(
                    old_breadcrumbs[-1].group
                ) >= _GROUP_ORDER.index(group):
                    # Trim old_breadcrumbs to match to group
                    old_breadcrumbs.pop(-1)
                if done:
                    break
            except Exception:
                LOG.exception("group loop")

        return tuple(new_breadcrumbs), changed

    def get_parent_breadcrumbs(
        self,
    ) -> tuple[Route, ...]:
        """Graft or create breadcrumbs by browser mode."""
        group = self.kwargs["group"]
        if group == FOLDER_GROUP:
            breadcrumbs, changed = self._breadcrumbs_graft_or_create_folder()
        elif group == STORY_ARC_GROUP:
            breadcrumbs, changed = self._breadcrumbs_graft_or_create_story_arc()
        else:
            breadcrumbs, changed = self._breadcrumbs_graft_or_create_group()

        if changed:
            self._breadcrumbs_save(breadcrumbs)

        return breadcrumbs[:-1] if breadcrumbs else ()

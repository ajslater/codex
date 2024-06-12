"""Browser breadcrumbs calculations."""

from contextlib import suppress
from types import MappingProxyType

from codex.logger.logging import get_logger
from codex.views.browser.paginate import BrowserPaginateView
from codex.views.const import FOLDER_GROUP, GROUP_NAME_MAP, GROUP_ORDER, STORY_ARC_GROUP
from codex.views.util import Route

LOG = get_logger(__name__)


class BrowserBreadcrumbsView(BrowserPaginateView):
    """Browser breadcrumbs calculations."""

    def _init_breadcrumbs(self, valid_groups):
        """Load breadcrumbs and determine if they should be searched for a graft."""
        breadcrumbs: list[Route] = list(self.params.get("breadcrumbs", []))
        old_breadcrumbs = [Route(**crumb) for crumb in breadcrumbs]
        invalid = not old_breadcrumbs or old_breadcrumbs[-1].group not in valid_groups
        if invalid:
            old_breadcrumbs = []
        return old_breadcrumbs, invalid

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
        group_crumb = Route(STORY_ARC_GROUP, pks, page, name)

        if old_breadcrumbs and old_breadcrumbs[-1] & group_crumb:
            # Graft. Hurray
            breadcrumbs = old_breadcrumbs
        else:
            # Create
            new_breadcrumbs = [group_crumb]
            if group_crumb.pks and 0 not in group_crumb.pks:
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

        pks = self.kwargs["pks"]
        page = self.kwargs["page"]
        folder = self.group_instance  # type: ignore
        name = folder.name if folder and pks else ""
        group_crumb = Route(FOLDER_GROUP, pks, page, name)
        new_breadcrumbs = []

        while True:
            branch = self._breadcrumb_find_branch(reversed_breadcrumbs, group_crumb)
            if branch and not branch[0].pks:
                # Branch must have the top as a head.
                # Graft. Hurray.
                new_breadcrumbs = branch + new_breadcrumbs
                break

            # Add head
            new_breadcrumbs = [group_crumb, *new_breadcrumbs]
            changed = True
            if not group_crumb.pks:
                break

            # parent next
            if not folder:
                break
            folder = folder.parent_folder
            if folder:
                group_crumb = Route(FOLDER_GROUP, (folder.pk,), 1, name=folder.name)
            else:
                group_crumb = Route(FOLDER_GROUP, (), 1, name="")

        breadcrumbs = new_breadcrumbs

        return tuple(breadcrumbs), changed

    def _get_breadcrumbs_group_crumb(self, group):
        """Create the crumb for this group."""
        gi = self.group_instance  # type: ignore
        if not gi:
            pks = ()
            page = 1
            name = ""
        if group == self.kwargs["group"]:
            # create self crumb
            pks = self.kwargs["pks"]
            page = self.kwargs["page"]
            name = gi.name if gi else ""
        else:
            page = 1
            if (attr := GROUP_NAME_MAP.get(group)) and (
                parent_group := getattr(gi, attr, None)
            ):
                pks = (parent_group.pk,)
                name = parent_group.name
            else:
                pks = ()
                name = ""

        return Route(group, pks, page, name)

    def _breadcrumbs_graft_or_create_group_crumb(
        self, group, old_breadcrumbs, new_breadcrumbs, changed
    ) -> tuple[bool, bool]:
        """Graft or create one browse group breadcrumb."""
        group_crumb = self._get_breadcrumbs_group_crumb(group)

        if old_breadcrumbs and (
            (group_crumb == old_breadcrumbs[-1])
            or (changed and (group_crumb & old_breadcrumbs[-1]))
            and not old_breadcrumbs[0].pks
        ):
            # Graft. Hurray
            new_breadcrumbs[0:0] = old_breadcrumbs
            done = True
        else:
            # Insert the new node
            new_breadcrumbs.insert(0, group_crumb)
            changed = True
            done = False
        return done, changed

    def _breadcrumbs_graft_or_create_group(self) -> tuple[tuple[Route, ...], bool]:
        """Graft or create browse group breadcrumbs."""
        old_breadcrumbs, changed = self._init_breadcrumbs(GROUP_ORDER)

        vng = self.valid_nav_groups  # type: ignore
        test_groups = tuple(reversed(vng[:-1]))
        new_breadcrumbs = []
        level = done = False
        try:
            browser_group_index = GROUP_ORDER.index(self.kwargs["group"])
        except ValueError:
            browser_group_index = -1

        for group in test_groups:
            try:
                with suppress(ValueError):
                    level = level or GROUP_ORDER.index(group) <= browser_group_index
                if level:
                    done, changed = self._breadcrumbs_graft_or_create_group_crumb(
                        group, old_breadcrumbs, new_breadcrumbs, changed
                    )
                try:
                    if old_breadcrumbs and GROUP_ORDER.index(
                        old_breadcrumbs[-1].group
                    ) >= GROUP_ORDER.index(group):
                        # Trim old_breadcrumbs to match to group
                        old_breadcrumbs.pop(-1)
                except ValueError:
                    old_breadcrumbs = []

                if done:
                    break
            except Exception:
                LOG.exception("group loop")

        return tuple(new_breadcrumbs), changed

    def get_breadcrumbs(
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

        return breadcrumbs

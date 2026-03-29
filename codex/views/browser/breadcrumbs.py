"""Browser breadcrumbs calculations."""

from types import MappingProxyType
from typing import TYPE_CHECKING

from django.db.models import QuerySet

from codex.models import (
    BrowserGroupModel,
    Comic,
    Imprint,
    Series,
    Volume,
)
from codex.models.groups import Publisher
from codex.views.browser.paginate import BrowserPaginateView
from codex.views.const import (
    FOLDER_GROUP,
    GROUP_MODEL_MAP,
    STORY_ARC_GROUP,
)
from codex.views.util import Route

if TYPE_CHECKING:
    from codex.models.groups import Folder

_GROUP_INSTANCE_SELECT_RELATED: MappingProxyType[
    type[BrowserGroupModel], tuple[str, ...]
] = MappingProxyType(
    {
        Comic: ("series", "volume"),
        Volume: ("series", "imprint", "publisher"),
        Series: ("imprint", "publisher"),
        Imprint: ("publisher",),
    }
)

# Map from group letter to the FK attribute chain for walking up the hierarchy.
# Each entry is (parent_group_letter, attribute_on_instance).
_GROUP_PARENT_CHAIN: MappingProxyType[str, tuple[tuple[str, str], ...]] = (
    MappingProxyType(
        {
            "v": (("s", "series"), ("i", "imprint"), ("p", "publisher")),
            "s": (("i", "imprint"), ("p", "publisher")),
            "i": (("p", "publisher"),),
            "p": (),
        }
    )
)


class BrowserBreadcrumbsView(BrowserPaginateView):
    """Browser breadcrumbs calculations."""

    def __init__(self, *args, **kwargs) -> None:
        """Set params for the type checker."""
        super().__init__(*args, **kwargs)
        # Use 0 to indicate unmemoized because None is a valid value
        self._group_instance: BrowserGroupModel | None | int = 0

    def _get_group_query(self, model):
        """Get the group query for the group instance."""
        pks = self.kwargs.get("pks")
        qs = model.objects.filter(pk__in=pks)
        if select_related := _GROUP_INSTANCE_SELECT_RELATED.get(model):
            qs = qs.select_related(*select_related)
        order_by = "name" if model is Volume else "sort_name"
        return qs.order_by(order_by)

    def _handle_group_query_missing_model(self, model) -> QuerySet:
        """Handle a missing model for the group instance."""
        group = self.kwargs.get("group")
        pks = self.kwargs.get("pks")
        page = self.kwargs.get("page")
        if group == "r" and not pks and page == 1:
            group_query = model.objects.none()
        else:
            reason = f"{group}__in={pks} does not exist!"
            self.raise_redirect(
                reason,
                route_mask={"group": group},
            )
        return group_query  # pyright: ignore[reportPossiblyUnboundVariable]

    @property
    def group_instance(self) -> BrowserGroupModel | None:
        """Memoize group instance for getting group names & counts."""
        if self._group_instance == 0:
            group = self.kwargs.get("group")
            model = GROUP_MODEL_MAP[group]
            pks = self.kwargs.get("pks")
            if model and pks and 0 not in pks:
                try:
                    group_query = self._get_group_query(model)
                except model.DoesNotExist:
                    group_query = self._handle_group_query_missing_model(model)
            else:
                if not model:
                    model = Publisher
                group_query = model.objects.none()
            self._group_instance = group_query.first()
        return self._group_instance  # pyright: ignore[reportReturnType], # ty: ignore[invalid-return-type]

    def _build_group_breadcrumbs(self) -> tuple[Route, ...]:
        """Build breadcrumbs for browse group mode by walking FK parents."""
        gi = self.group_instance
        group = self.kwargs["group"]
        pks = self.kwargs["pks"]
        page = self.kwargs["page"]

        if not gi:
            return (Route("r", (), 1, ""),)

        # Start with current crumb
        crumbs: list[Route] = [Route(group, pks, page, gi.name)]

        # Walk up the parent chain via FKs
        vng = self.valid_nav_groups
        parent_chain = _GROUP_PARENT_CHAIN.get(group, ())
        for parent_group, attr in parent_chain:
            if parent_group not in vng:
                continue
            if parent := getattr(gi, attr, None):
                crumbs.append(Route(parent_group, (parent.pk,), 1, parent.name))
            else:
                crumbs.append(Route(parent_group, (), 1, ""))

        # Always add root
        crumbs.append(Route("r", (), 1, ""))
        crumbs.reverse()
        return tuple(crumbs)

    def _build_folder_breadcrumbs(self) -> tuple[Route, ...]:
        """Build breadcrumbs for folder mode by walking parent_folder FKs."""
        pks = self.kwargs["pks"]
        page = self.kwargs["page"]
        folder: Folder | None = self.group_instance  # pyright: ignore[reportAssignmentType], # ty: ignore[invalid-assignment]
        name = folder.name if folder and pks else ""

        crumbs: list[Route] = [Route(FOLDER_GROUP, pks, page, name)]

        # Walk up the parent_folder chain
        while folder and folder.parent_folder:
            folder = folder.parent_folder
            crumbs.append(Route(FOLDER_GROUP, (folder.pk,), 1, folder.name))  # pyright: ignore[reportOptionalMemberAccess]

        # Add folder root if not already there
        if crumbs[-1].pks:
            crumbs.append(Route(FOLDER_GROUP, (), 1, ""))

        crumbs.reverse()
        return tuple(crumbs)

    def _build_story_arc_breadcrumbs(self) -> tuple[Route, ...]:
        """Build breadcrumbs for story arc mode."""
        pks = self.kwargs["pks"]
        page = self.kwargs["page"]
        gi = self.group_instance
        name = gi.name if gi else ""

        crumbs: list[Route] = [Route(STORY_ARC_GROUP, pks, page, name)]

        # Add story arc root if viewing a specific arc
        if pks and 0 not in pks:
            crumbs.insert(0, Route(STORY_ARC_GROUP, (), 1, ""))

        return tuple(crumbs)

    def get_breadcrumbs(self) -> tuple[Route, ...]:
        """Compute breadcrumbs by browser mode from FK hierarchy."""
        group = self.kwargs["group"]
        if group == FOLDER_GROUP:
            return self._build_folder_breadcrumbs()
        if group == STORY_ARC_GROUP:
            return self._build_story_arc_breadcrumbs()
        return self._build_group_breadcrumbs()

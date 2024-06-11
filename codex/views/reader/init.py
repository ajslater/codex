"""Views for reading comic books."""

from copy import deepcopy
from types import MappingProxyType

from codex.logger.logging import get_logger
from codex.models import Comic
from codex.serializers.reader import (
    ReaderViewInputSerializer,
)
from codex.views.const import FOLDER_GROUP, GROUP_RELATION, STORY_ARC_GROUP
from codex.views.session import SessionView
from codex.views.util import reparse_json_query_params

LOG = get_logger(__name__)
VALID_ARC_GROUPS = frozenset({"s", "v", "f", "a"})
_JSON_KEYS = frozenset({"arc", "breadcrumbs", "show"})
_BROWSER_SESSION_DEFAULTS = SessionView.SESSION_DEFAULTS[
    SessionView.BROWSER_SESSION_KEY
]
_DEFAULT_PARAMS = {
    "breadcrumbs": _BROWSER_SESSION_DEFAULTS["breadcrumbs"],
    "show": _BROWSER_SESSION_DEFAULTS["show"],
    "top_group": _BROWSER_SESSION_DEFAULTS["top_group"],
}


class ReaderInitView(SessionView):
    """Reader initialization."""

    input_serializer_class = ReaderViewInputSerializer

    def __init__(self, *args, **kwargs):
        """Initialize instance vars."""
        super().__init__(*args, **kwargs)
        self.group_pks: dict[str, tuple[int, ...]] = {}

    def get_group_pks_from_breadcrumbs(self, groups):
        """Get Multi-Group pks from the breadcrumbs."""
        for group in groups:
            if pks := self.group_pks.get(group):
                return group, pks
        breadcrumbs: tuple = self.params.get("breadcrumbs")  # type: ignore
        if not breadcrumbs:
            return None, ()

        index = len(breadcrumbs) - 1
        min_index = max(index - 1, 0) if FOLDER_GROUP in groups else 0
        crumb_group = None
        while index > min_index:
            crumb = breadcrumbs[index]
            crumb_group = crumb.get("group")
            if crumb_group in groups:
                self.group_pks[crumb_group] = crumb.get("pks", ())
                break
            index -= 1
        else:
            for group in groups:
                self.group_pks[group] = ()

        if crumb_group and (pks := self.group_pks.get(crumb_group)):
            return crumb_group, pks
        return None, ()

    def _ensure_arc_contains_comic(self, params):
        """Arc sanity check."""
        arc = params.get("arc", {})
        pk = self.kwargs["pk"]
        arc_group = arc.get("group")
        arc_pk = arc.get("pk")
        valid = False
        if rel := GROUP_RELATION.get(arc_group):
            valid = Comic.objects.filter(pk=pk, **{rel: arc_pk}).exists()
        if not valid:
            LOG.warning(f"Invalid arc {arc} submitted to reader for comic {pk}.")
            params.pop("arc", None)

    def _ensure_arc(self, params):
        """arc.group validation."""
        # Can't be in the serializer
        arc = params.get("arc", {})

        if arc.get("group") not in VALID_ARC_GROUPS:
            top_group = params["top_group"]
            if top_group in (FOLDER_GROUP, STORY_ARC_GROUP):
                search_groups = (top_group,)
            else:
                search_groups = ("v", "s")

            group, pks = self.get_group_pks_from_breadcrumbs(search_groups)
            if not group:
                group = "s"

            arc["group"] = group
            if pks:
                arc["pks"] = pks

        params["arc"] = arc

    def _parse_params(self):
        data = self.request.GET
        data = reparse_json_query_params(self.request.GET, _JSON_KEYS)
        serializer = self.input_serializer_class(data=data)
        serializer.is_valid(raise_exception=True)

        params = deepcopy(_DEFAULT_PARAMS)
        if serializer.validated_data:
            params.update(serializer.validated_data)  # type: ignore
        self._ensure_arc_contains_comic(params)
        self._ensure_arc(params)

        self.params = MappingProxyType(params)

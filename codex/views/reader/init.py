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
VALID_ARC_GROUPS = "pisvfa"
_JSON_KEYS = frozenset({"arc", "breadcrumbs", "browser_arc", "show"})
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

    def _set_group_pks_from_breadcrumbs(self, groups, breadcrumbs):
        """Set Multi-Group pks from breadcrumbs to the cache."""
        index = len(breadcrumbs) - 1
        min_index = max(index - 1, 0) if FOLDER_GROUP in groups else 0
        while index > min_index:
            crumb = breadcrumbs[index]
            crumb_group = crumb.get("group")
            if crumb_group in groups:
                pks = crumb.get("pks", ())
                self.group_pks[crumb_group] = pks
                break
            index -= 1
        else:
            crumb_group = ""
            pks = ()
            for group in groups:
                self.group_pks[group] = pks
        return crumb_group, pks

    def get_group_pks_from_breadcrumbs(self, groups):
        """Get Multi-Group pks from the breadcrumbs."""
        # Return cached values
        for group in groups:
            if pks := self.group_pks.get(group):
                return group, pks

        # Validate input
        breadcrumbs: tuple = self.params.get("breadcrumbs")  # type: ignore
        if not breadcrumbs:
            return "", ()

        return self._set_group_pks_from_breadcrumbs(groups, breadcrumbs)

    def _ensure_arc_contains_comic(self, params):
        """Arc sanity check."""
        arc = params.get("arc")
        if not arc:
            return
        pk = self.kwargs["pk"]
        arc_group = arc.get("group")
        arc_pks = arc.get("pks")
        valid = False
        if rel := GROUP_RELATION.get(arc_group):
            arc_filter = {rel: arc_pks}
            valid = Comic.objects.filter(pk=pk, **arc_filter).exists()
        if not valid:
            LOG.warning(f"Invalid arc {arc} submitted to reader for comic {pk}.")
            params.pop("arc", None)

    def _ensure_arc(self, params):
        """arc.group validation."""
        # Can't be in the serializer
        arc = params.get("arc", {})

        arc_group = arc.get("group", "")
        arc_pks = arc.get("pks", ())
        if arc_group not in VALID_ARC_GROUPS or not arc_pks:
            top_group = params["top_group"]
            if top_group in FOLDER_GROUP + STORY_ARC_GROUP:
                search_groups = (top_group,)
            else:
                search_groups = "vsip"

            group, pks = self.get_group_pks_from_breadcrumbs(search_groups)
            if not group:
                group = "s"

            arc["group"] = group
            if pks:
                arc["pks"] = pks

        params["arc"] = arc

    def _parse_params(self):
        try:
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
        except Exception:
            LOG.exception("validate")
            raise

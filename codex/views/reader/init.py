"""Views for reading comic books."""

from copy import deepcopy
from types import MappingProxyType

from codex.logger.logging import get_logger
from codex.serializers.reader import (
    ReaderViewInputSerializer,
)
from codex.views.const import FOLDER_GROUP, STORY_ARC_GROUP
from codex.views.session import SessionView
from codex.views.util import reparse_json_query_params

LOG = get_logger(__name__)
VALID_ARC_GROUPS = frozenset({"f", "s", "a"})
_JSON_KEYS = frozenset({"arc", "breadcrumbs", "show"})
_BROWSER_SESSION_DEFAULTS = SessionView.SESSION_DEFAULTS[
    SessionView.BROWSER_SESSION_KEY
]
_DEFAULT_PARAMS = {
    "breadcrumbs": _BROWSER_SESSION_DEFAULTS["breadcrumbs"],
    "show": _BROWSER_SESSION_DEFAULTS["show"],
    "top_group": _BROWSER_SESSION_DEFAULTS["top_group"],
}
_MIN_CRUMB_WALKBACK_LEN = 3


class ReaderInitView(SessionView):
    """Reader initialization."""

    input_serializer_class = ReaderViewInputSerializer

    def __init__(self, *args, **kwargs):
        """Initialize instance vars."""
        super().__init__(*args, **kwargs)
        self.series_pks: tuple[int, ...] = ()

    def get_series_pks_from_breadcrumbs(self, breadcrumbs):
        """Get Multi-Group pks from the breadcrumbs."""
        if self.series_pks:
            return self.series_pks
        if breadcrumbs:
            crumb = breadcrumbs[-1]
            crumb_group = crumb.get("group")
            if crumb_group == "v" and len(breadcrumbs) >= _MIN_CRUMB_WALKBACK_LEN:
                crumb = breadcrumbs[-2]
                crumb_group = crumb.get("group")
            if crumb_group == "s":
                self.series_pks = crumb.get("pks", ())

        return self.series_pks

    def _ensure_arc(self, params):
        """arc.group validation."""
        # Can't be in the serializer
        arc = params.get("arc", {})
        if arc.get("group") not in VALID_ARC_GROUPS:
            top_group = params["top_group"]
            if top_group in (FOLDER_GROUP, STORY_ARC_GROUP):
                arc["group"] = top_group
            else:
                arc["group"] = "s"
                breadcrumbs = params["breadcrumbs"]
                series_pks = self.get_series_pks_from_breadcrumbs(breadcrumbs)
                if series_pks:
                    arc["pks"] = series_pks

        params["arc"] = arc

    def _parse_params(self):
        data = self.request.GET
        data = reparse_json_query_params(self.request.GET, _JSON_KEYS)
        serializer = self.input_serializer_class(data=data)
        serializer.is_valid(raise_exception=True)

        params = deepcopy(_DEFAULT_PARAMS)
        if serializer.validated_data:
            params.update(serializer.validated_data)  # type: ignore
        self._ensure_arc(params)

        self.params = MappingProxyType(params)

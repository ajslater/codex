"""Views for reading comic books."""

from types import MappingProxyType
from typing import Any

from loguru import logger

from codex.serializers.fields.reader import VALID_ARC_GROUPS
from codex.serializers.reader import ReaderViewInputSerializer
from codex.util import mapping_to_dict
from codex.views.session import SessionView
from codex.views.util import reparse_json_query_params

_JSON_KEYS = frozenset({"arc"})


class ReaderParamsView(SessionView):
    """Reader initialization."""

    input_serializer_class = ReaderViewInputSerializer

    def __init__(self, *args, **kwargs):
        """Initialize instance vars."""
        super().__init__(*args, **kwargs)
        self._group_pks: dict[str, tuple[int, ...]] = {}
        self._params: MappingProxyType[str, Any] | None = None

    def _ensure_arc_group(self, params: dict[str, Any]):
        arc = params.get("arc", {})
        group = arc.get("group", "")
        if not group:
            top_group = self.get_from_session(
                "top_group", session_key=self.BROWSER_SESSION_KEY
            )
            group = "s" if top_group in "rpi" else top_group
        if group not in VALID_ARC_GROUPS:
            group = "s"
        params["arc"]["group"] = group

    @staticmethod
    def _ensure_arc_ids(params: dict[str, Any]):
        arc = params.get("arc", {})
        if ids := arc.get("ids"):
            ids = tuple(sorted(set(filter(lambda x: x > 0, ids))))
        else:
            ids = ()
        params["arc"]["ids"] = ids

    def _ensure_arc(self, params: dict[str, Any]) -> None:
        """Ensure the group is valid."""
        if "arc" not in params:
            params["arc"] = {}

        self._ensure_arc_group(params)
        self._ensure_arc_ids(params)

    @property
    def params(self):
        """Memoized params property."""
        if self._params is None:
            try:
                data = reparse_json_query_params(self.request.GET, _JSON_KEYS)
                serializer = self.input_serializer_class(data=data)
                serializer.is_valid(raise_exception=True)
                params: dict = mapping_to_dict(serializer.validated_data)  # pyright: ignore[reportAssignmentType]
                self._ensure_arc(params)
                self._params = MappingProxyType(params)
            except Exception:
                logger.exception("validate")
                raise
        return self._params

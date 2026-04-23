"""Views for reading comic books."""

from types import MappingProxyType
from typing import Any

from loguru import logger

from codex.serializers.fields.reader import VALID_ARC_GROUPS
from codex.serializers.reader import ReaderViewInputSerializer
from codex.views.reader.settings import ReaderSettingsBaseView


class ReaderParamsView(ReaderSettingsBaseView):
    """Reader initialization."""

    input_serializer_class = ReaderViewInputSerializer

    def __init__(self, *args, **kwargs) -> None:
        """Initialize instance vars."""
        super().__init__(*args, **kwargs)
        self._group_pks: dict[str, tuple[int, ...]] = {}
        self._params: MappingProxyType[str, Any] | None = None

    def _ensure_arc_group(self, params: dict[str, Any]) -> None:
        arc = params.get("arc", {})
        group = arc.get("group", "")
        if not group:
            top_group: str = self.get_from_settings(  # pyright: ignore[reportAssignmentType]
                "top_group", browser=True
            )
            group = "s" if top_group in "rpi" else top_group
        if group not in VALID_ARC_GROUPS:
            group = "s"
        params["arc"]["group"] = group

    @staticmethod
    def _ensure_arc_ids(params: dict[str, Any]) -> None:
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
                serializer = self.input_serializer_class(data=self.request.GET)
                serializer.is_valid(raise_exception=True)

                params = self.load_params_from_settings()
                if serializer.validated_data:
                    params.update(serializer.validated_data)
                self._ensure_arc(params)
                self.save_params_to_settings(params)
                self._params = MappingProxyType(params)
            except Exception:
                logger.exception("validate")
                raise
        return self._params

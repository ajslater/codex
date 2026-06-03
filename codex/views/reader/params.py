"""Views for reading comic books."""

from types import MappingProxyType
from typing import Any

from loguru import logger

from codex.collection import Collection
from codex.serializers.fields.reader import VALID_ARC_COLLECTIONS
from codex.serializers.reader import ReaderViewInputSerializer
from codex.views.reader.settings import ReaderSettingsBaseView

# Top collections with no arc of their own — they read within the series scope.
_SERIES_COLLAPSE_TOP_COLLECTIONS = frozenset(
    {Collection.ROOT, Collection.PUBLISHER, Collection.IMPRINT}
)


class ReaderParamsView(ReaderSettingsBaseView):
    """Reader initialization."""

    input_serializer_class = ReaderViewInputSerializer

    def __init__(self, *args, **kwargs) -> None:
        """Initialize instance vars."""
        super().__init__(*args, **kwargs)
        self._collection_pks: dict[str, tuple[int, ...]] = {}
        self._params: MappingProxyType[str, Any] | None = None

    def _ensure_arc_collection(self, params: dict[str, Any]) -> None:
        arc = params.get("arc", {})
        collection = arc.get("collection", "")
        if not collection:
            top_collection: str = self.get_from_settings(  # pyright: ignore[reportAssignmentType]
                "top_collection", browser=True
            )
            collection = (
                Collection.SERIES
                if top_collection in _SERIES_COLLAPSE_TOP_COLLECTIONS
                else top_collection
            )
        if collection not in VALID_ARC_COLLECTIONS:
            collection = Collection.SERIES
        params["arc"]["collection"] = collection

    @staticmethod
    def _ensure_arc_ids(params: dict[str, Any]) -> None:
        arc = params.get("arc", {})
        if ids := arc.get("ids"):
            ids = tuple(sorted(set(filter(lambda x: x > 0, ids))))
        else:
            ids = ()
        params["arc"]["ids"] = ids

    def _ensure_arc(self, params: dict[str, Any]) -> None:
        """Ensure the collection is valid."""
        if "arc" not in params:
            params["arc"] = {}

        self._ensure_arc_collection(params)
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

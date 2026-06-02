"""Get the mtimes for the submitted groups."""

from drf_spectacular.utils import extend_schema
from rest_framework.response import Response
from rest_framework.serializers import BaseSerializer

from codex.models.groups import Publisher
from codex.serializers.browser.mtime import CollectionsMtimeSerializer, MtimeSerializer
from codex.util import max_none
from codex.views.browser.collection_mtime import BrowserCollectionMtimeView
from codex.views.const import COLLECTION_MODEL_MAP


class MtimeView(BrowserCollectionMtimeView):
    """Get the mtimes for the submitted groups."""

    input_serializer_class: type[CollectionsMtimeSerializer] = (  # pyright: ignore[reportIncompatibleVariableOverride]
        CollectionsMtimeSerializer
    )
    serializer_class: type[BaseSerializer] | None = MtimeSerializer

    TARGET: str = "mtime"

    def _get_collection_mtime(self, item):
        """Get one group's mtimes."""
        group = item["collection"]
        pks = item["pks"]

        model = COLLECTION_MODEL_MAP[group]
        if not model:
            model = Publisher

        return self.get_collection_mtime(model, group, pks)

    def get_max_collections_mtime(self):
        """Get max mtime for all groups."""
        max_mtime = None

        for item in self.params["groups"]:
            mtime = self._get_collection_mtime(item)
            max_mtime = max_none(max_mtime, mtime)
        return max_mtime

    @extend_schema(parameters=[CollectionsMtimeSerializer])
    def get(self, *args, **kwargs) -> Response:
        """Get the mtimes for the submitted groups."""
        max_mtime = self.get_max_collections_mtime()

        # Serialize Response
        result = {"max_mtime": max_mtime}
        serializer = self.get_serializer(result)
        return Response(serializer.data)

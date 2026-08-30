"""Get the mtimes for the submitted collections."""

from cachalot.api import cachalot_disabled
from django.db.models.aggregates import Max
from django.db.models.functions import Greatest
from django.db.utils import OperationalError
from drf_spectacular.utils import extend_schema
from rest_framework.response import Response
from rest_framework.serializers import BaseSerializer

from codex.collection import READER_REPRINT_COLLECTION
from codex.models.collections import Publisher
from codex.models.named import Reprint
from codex.serializers.browser.mtime import CollectionsMtimeSerializer, MtimeSerializer
from codex.util import max_none
from codex.views.browser.collection_mtime import BrowserCollectionMtimeView
from codex.views.const import (
    COLLECTION_MODEL_MAP,
    EPOCH_START,
    EPOCH_START_DATETIMEFIELD,
)


class MtimeView(BrowserCollectionMtimeView):
    """Get the mtimes for the submitted collections."""

    input_serializer_class: type[CollectionsMtimeSerializer] = (  # pyright: ignore[reportIncompatibleVariableOverride]
        CollectionsMtimeSerializer
    )
    serializer_class: type[BaseSerializer] | None = MtimeSerializer

    TARGET: str = "mtime"

    def _get_reprint_mtime(self, pks):
        """
        Get the mtime of an alternate series the reader is reading.

        ``Reprint`` isn't a browse collection, so it has no filtered
        queryset to aggregate — read its rows directly.
        ``TimestampUpdater`` keeps ``updated_at`` current when a member
        comic changes, which is what makes this probe meaningful.
        """
        if not pks:
            return None
        qs = Reprint.objects.filter(pk__in=pks)
        agg_terms = [
            Max("updated_at", default=EPOCH_START_DATETIMEFIELD),
            self.get_max_bookmark_updated_at_aggregate(
                Reprint, default=EPOCH_START_DATETIMEFIELD
            ),
        ]
        try:
            with cachalot_disabled():
                mtime = qs.aggregate(max=Greatest(*agg_terms))["max"]
            if mtime == NotImplemented:
                mtime = None
            elif not mtime:
                mtime = EPOCH_START
        except OperationalError as exc:
            self._handle_operational_error(exc)
            mtime = None
        return mtime

    def _get_collection_mtime(self, item):
        """Get one collection's mtimes."""
        collection = item["collection"]
        pks = item["pks"]

        if collection == READER_REPRINT_COLLECTION:
            return self._get_reprint_mtime(pks)

        model = COLLECTION_MODEL_MAP[collection]
        if not model:
            model = Publisher

        return self.get_collection_mtime(model, collection, pks)

    def get_max_collections_mtime(self):
        """Get max mtime for all collections."""
        max_mtime = None

        for item in self.params["collections"]:
            mtime = self._get_collection_mtime(item)
            max_mtime = max_none(max_mtime, mtime)
        return max_mtime

    @extend_schema(parameters=[CollectionsMtimeSerializer])
    def get(self, *args, **kwargs) -> Response:
        """Get the mtimes for the submitted collections."""
        max_mtime = self.get_max_collections_mtime()

        # Serialize Response
        result = {"max_mtime": max_mtime}
        serializer = self.get_serializer(result)
        return Response(serializer.data)

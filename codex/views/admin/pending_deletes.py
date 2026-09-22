"""Admin Pending Deletes View."""

from django.utils import timezone
from rest_framework.exceptions import NotFound
from rest_framework.response import Response

from codex.librarian.mp_queue import LIBRARIAN_QUEUE
from codex.librarian.pending_deletes import (
    PENDING_DELETE_WINDOW,
    clear_stamps,
    publish_revival,
)
from codex.librarian.scribe.tasks import UpdateCollectionsTask
from codex.models import Comic, Folder
from codex.serializers.admin.pending_deletes import PendingDeleteSerializer
from codex.views.admin.auth import AdminAPIView

#: The two models that can carry a stamp, keyed by the ``collection``
#: segment the client sends back on a revive.
_MODELS = {"comics": Comic, "folders": Folder}


def _rows(model, collection: str) -> list[dict]:
    """Every stamped row of one model, oldest stamp first."""
    qs = (
        model.objects.filter(missing_since__isnull=False)
        .select_related("library")
        .only("pk", "path", "missing_since", "library")
        .order_by("missing_since", "pk")
    )
    return [
        {
            "pk": row.pk,
            "collection": collection,
            "path": row.path,
            "library_id": row.library_id,
            "missing_since": row.missing_since,
            # Computed here rather than in the client so one definition
            # of the window exists. It is the earliest the nightly run
            # could take it; the real delete is at the next run after.
            "reap_after": row.missing_since + PENDING_DELETE_WINDOW,
        }
        for row in qs
    ]


class AdminPendingDeletesView(AdminAPIView):
    """
    List the rows the retention window is holding.

    The only window onto this state. The visibility filter hides a
    stamped row from every browsing surface with no staff exemption, so
    without this endpoint the state would be invisible to everyone and
    an admin could neither revive a row nor force an early delete. That
    is why this is a plain ``AdminAPIView`` reading the models directly:
    it must see exactly what the browser must not.
    """

    serializer_class = PendingDeleteSerializer

    def get(self, _request, *_args, **_kwargs) -> Response:
        """Return every pending delete, comics and folders together."""
        rows = _rows(Comic, "comics") + _rows(Folder, "folders")
        rows.sort(key=lambda row: (row["missing_since"], row["collection"], row["pk"]))
        serializer = self.serializer_class(rows, many=True)
        return Response(serializer.data)


class AdminPendingDeleteReviveView(AdminAPIView):
    """Clear one row's stamp by hand."""

    def post(self, _request, collection: str, pk: int, *_args, **_kwargs) -> Response:
        """
        Put a row back, whether or not its file has returned.

        The poller revives a row on its own once the path is readable
        again. This is for the case it cannot reach: a path that will
        not come back on its own schedule, or an admin who simply wants
        the row to stop counting down.
        """
        model = _MODELS.get(collection)
        if model is None:
            reason = f"Unknown collection {collection!r}"
            raise NotFound(detail=reason)
        if not clear_stamps(model, pk=pk):
            reason = f"No pending delete for {collection} {pk}"
            raise NotFound(detail=reason)
        comic_pks = (pk,) if model is Comic else ()
        publish_revival(LIBRARIAN_QUEUE, comic_pks)
        self._restamp_collections()
        return Response({"detail": f"Revived {collection} {pk}."})

    @staticmethod
    def _restamp_collections() -> None:
        """
        Re-stamp parent collections through the scribe.

        The browser's refresh probe reads a collection's own
        ``updated_at``, not its comics'. A view has no write lock, so
        this goes through the queue rather than running inline.
        """
        LIBRARIAN_QUEUE.put(UpdateCollectionsTask(start_time=timezone.now()))

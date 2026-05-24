"""Admin Tag Write View."""

from rest_framework.response import Response
from rest_framework.status import HTTP_202_ACCEPTED

from codex.librarian.mp_queue import LIBRARIAN_QUEUE
from codex.librarian.scribe.tasks import BulkTagWriteTask
from codex.models.comic import Comic
from codex.serializers.admin.tagging import TagWriteRequestSerializer
from codex.views.admin.auth import AdminAPIView
from codex.views.const import COMIC_GROUP, GROUP_RELATION


def _resolve_comic_pks(group: str, pks: list[str]) -> frozenset[int]:
    """Resolve a group + pks to a set of comic primary keys."""
    int_pks = frozenset(int(pk) for pk in pks if pk.isdigit())
    if not int_pks:
        return frozenset()

    if group == COMIC_GROUP:
        return int_pks

    rel = GROUP_RELATION.get(group)
    if not rel:
        return frozenset()

    filter_key = f"{rel}__in"
    return frozenset(
        Comic.objects.filter(**{filter_key: int_pks}).values_list("pk", flat=True)
    )


class AdminTagWriteView(AdminAPIView):
    """POST to write tags to comic archives."""

    def post(self, request):
        """Validate request and enqueue a BulkTagWriteTask."""
        serializer = TagWriteRequestSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data

        comic_pks = _resolve_comic_pks(data["group"], data["pks"])
        if not comic_pks:
            return Response({"detail": "No comics matched."}, status=400)

        task = BulkTagWriteTask(
            comic_pks=comic_pks,
            patch=data.get("patch"),
            mode=data["mode"],
            formats=tuple(data["formats"]),
        )
        LIBRARIAN_QUEUE.put(task)
        return Response(
            {"detail": f"Tag write queued for {len(comic_pks)} comics."},
            status=HTTP_202_ACCEPTED,
        )

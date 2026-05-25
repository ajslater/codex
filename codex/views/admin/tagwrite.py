"""Admin Tag Write View."""

from rest_framework.response import Response
from rest_framework.status import HTTP_202_ACCEPTED

from codex.librarian.mp_queue import LIBRARIAN_QUEUE
from codex.librarian.scribe.tasks import BulkTagWriteTask
from codex.models.admin import ComicboxTaggingDefaults
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


class AdminParseIdentifierURLView(AdminAPIView):
    """Parse a URL into an identifier source, type, and key."""

    def post(self, request):
        """Parse a URL and return identifier components."""
        from comicbox.identifiers.identifiers import IDENTIFIER_PARTS_MAP

        url = request.data.get("url", "").strip()
        if not url:
            return Response({"detail": "No URL provided."}, status=400)

        for source_enum, parts in IDENTIFIER_PARTS_MAP.items():
            if parts.domain in url:
                try:
                    id_type, id_key = parts.parse_url_path(url)
                    return Response({
                        "source": source_enum.value,
                        "id_type": id_type,
                        "key": id_key,
                    })
                except Exception:
                    break

        return Response(
            {"detail": "Could not parse URL. No matching source found."},
            status=400,
        )


class AdminTagWritePreflightView(AdminAPIView):
    """Check how many comics need conversion before writing."""

    def post(self, request):
        """Return conversion stats for the given group+pks."""
        serializer = TagWriteRequestSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data

        comic_pks = _resolve_comic_pks(data["group"], data["pks"])
        if not comic_pks:
            return Response({"total": 0, "need_conversion": 0})

        need_conversion = Comic.objects.filter(
            pk__in=comic_pks,
            file_type__in=("CBR", "CB7", "CBT"),
        ).count()

        try:
            defaults = ComicboxTaggingDefaults.objects.get(pk=1)
            delete_original = defaults.delete_original
        except ComicboxTaggingDefaults.DoesNotExist:
            delete_original = False

        return Response({
            "total": len(comic_pks),
            "need_conversion": need_conversion,
            "delete_original": delete_original,
        })


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

        req_delete = data.get("delete_original")
        if req_delete is not None:
            delete_original = req_delete
        else:
            try:
                defaults = ComicboxTaggingDefaults.objects.get(pk=1)
                delete_original = defaults.delete_original
            except ComicboxTaggingDefaults.DoesNotExist:
                delete_original = False

        task = BulkTagWriteTask(
            comic_pks=comic_pks,
            patch=data.get("patch"),
            mode=data["mode"],
            formats=tuple(data["formats"]),
            delete_original=delete_original,
        )
        LIBRARIAN_QUEUE.put(task)
        return Response(
            {"detail": f"Tag write queued for {len(comic_pks)} comics."},
            status=HTTP_202_ACCEPTED,
        )

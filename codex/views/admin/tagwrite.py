"""Admin Tag Write View."""

import json
from collections.abc import Sequence
from pathlib import Path
from types import MappingProxyType
from typing import override

from rest_framework.permissions import BasePermission, IsAdminUser
from rest_framework.response import Response
from rest_framework.status import HTTP_202_ACCEPTED

from codex.librarian.mp_queue import LIBRARIAN_QUEUE
from codex.librarian.scribe.tagwrite_rename import build_predict_config, plan_rename
from codex.librarian.scribe.tasks import BulkTagWriteTask
from codex.models.admin import ComicboxTaggingDefaults
from codex.models.comic import Comic
from codex.serializers.admin.tagging import TagWriteRequestSerializer
from codex.views.admin.auth import AdminAPIView
from codex.views.admin.identifier_parse import parse_identifier_url
from codex.views.browser.filters.filter import BrowserFilterView

#: Cap on how many per-comic rename previews the preflight builds — each opens
#: an archive, so a huge multi-selection can't stall the request.
_FILENAME_PREVIEW_LIMIT = 100


class FilteredComicPksView(BrowserFilterView):
    """
    Resolve a browse collection + pks to the *filtered* comic pks.

    Admin tag-write / online-tag select comics exactly like the browser:
    a collection plus the user's active filters (file_type, read/unread, ACL,
    favorite, search). Resolving through ``get_filtered_queryset`` keeps
    writes confined to the comics the user actually selected — never the
    unfiltered remainder of the collection. Mirrors
    :class:`~codex.views.browser.force_update.ForceUpdateView`.
    """

    permission_classes: Sequence[type[BasePermission]] = (IsAdminUser,)
    TARGET: str = "force_update"  # recursive folder rel + filter semantics

    def __init__(self, *args, **kwargs) -> None:
        """Init group ACL state."""
        super().__init__(*args, **kwargs)
        self.init_group_acl()
        #: Count of resolved comics dropped because their library is read-only.
        #: Set by the most recent ``resolve_comic_pks`` call.
        self.skipped_read_only: int = 0

    @property
    @override
    def params(self):
        """Load active browser filters from settings without persisting."""
        if self._params is None:
            self._params = MappingProxyType(self.load_params_from_settings())
        return self._params

    def resolve_comic_pks(self, collection: str, pks) -> frozenset[int]:
        """
        Resolve collection+pks to *editable* filtered comic pks.

        Comics in read-only libraries are dropped here — the single funnel both
        tag-write and online-tag flow through — so no read-only archive is ever
        enqueued for a write, regardless of the UI. The number dropped is stashed
        on ``self.skipped_read_only`` so callers can report it to the user.
        """
        self.skipped_read_only = 0
        int_pks = tuple(sorted({int(pk) for pk in pks if str(pk).isdigit()}))
        if not int_pks:
            return frozenset()
        self.kwargs["collection"] = collection
        self.kwargs["pks"] = int_pks
        qs = self.get_filtered_queryset(Comic, collection=collection, pks=int_pks)
        rows = tuple(qs.values_list("pk", "library__read_only"))
        editable_pks = frozenset(pk for pk, read_only in rows if not read_only)
        self.skipped_read_only = len(rows) - len(editable_pks)
        return editable_pks


class AdminParseIdentifierURLView(AdminAPIView):
    """Parse a URL into an identifier source, type, and key."""

    def post(self, request):
        """Parse a URL and return identifier components."""
        url = request.data.get("url", "").strip()
        if not url:
            return Response({"detail": "No URL provided."}, status=400)

        parsed = parse_identifier_url(url)
        if parsed is None:
            return Response(
                {"detail": "Could not parse URL. No matching source found."},
                status=400,
            )
        source, id_type, id_key = parsed
        return Response({"source": source, "id_type": id_type, "key": id_key})


class AdminTagWritePreflightView(FilteredComicPksView):
    """Check how many comics need conversion before writing."""

    @staticmethod
    def _preview_one(pk: int, old_path: Path, patch: dict | None, config) -> str:
        """
        Return the name this comic ends up with, or "" if it can't be built.

        Derived through the same planner the rename itself uses, so the
        dialog cannot promise a name the write won't produce. Shows the
        *final* name, which for an archive the write will repack is the
        converted CBZ rather than the interim one. Opens the archive (I/O).
        """
        try:
            plan = plan_rename(pk, old_path, patch, config)
        except Exception:
            return ""
        return plan.final_path.name if plan else ""

    def _filename_previews(
        self,
        comic_pks: frozenset[int],
        patch_str: str,
        delete_keys: tuple[str, ...] = (),
        mode: str = "additive",
    ) -> list[dict[str, str]]:
        """Preview the rename (old → new) for each selected comic, capped."""
        patch = json.loads(patch_str or "null")
        # Pending cleared fields must vanish from the previewed name exactly
        # as the real write (BulkWriteItem.delete_keys) will clear them, and
        # the write mode decides whether a patch value replaces or extends
        # what the archive already holds.
        config = build_predict_config(delete_keys, mode)
        comics = (
            Comic.objects.filter(pk__in=comic_pks)
            .only("pk", "path")
            .order_by("pk")[:_FILENAME_PREVIEW_LIMIT]
        )
        previews: list[dict[str, str]] = []
        for comic in comics:
            old_path = Path(comic.path)
            previews.append(
                {
                    "old": old_path.name,
                    "new": self._preview_one(comic.pk, old_path, patch, config),
                }
            )
        return previews

    def post(self, request):
        """Return conversion stats for the given collection+pks."""
        serializer = TagWriteRequestSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data

        comic_pks = self.resolve_comic_pks(data["collection"], data["pks"])
        if not comic_pks:
            return Response(
                {"total": 0, "need_conversion": 0, "skipped": self.skipped_read_only}
            )

        need_conversion = Comic.objects.filter(
            pk__in=comic_pks,
            file_type__in=("CBR", "CB7", "CBT"),
        ).count()

        try:
            defaults = ComicboxTaggingDefaults.objects.get(pk=1)
            delete_original = defaults.delete_original
            rename = defaults.rename_files
        except ComicboxTaggingDefaults.DoesNotExist:
            delete_original = False
            rename = False

        return Response(
            {
                "total": len(comic_pks),
                "need_conversion": need_conversion,
                "delete_original": delete_original,
                "rename": rename,
                "filename_previews": self._filename_previews(
                    comic_pks,
                    data.get("patch") or "",
                    tuple(data.get("delete_keys") or ()),
                    data["mode"],
                ),
                "skipped": self.skipped_read_only,
            }
        )


class AdminTagWriteView(FilteredComicPksView):
    """POST to write tags to comic archives."""

    def post(self, request):
        """Validate request and enqueue a BulkTagWriteTask."""
        serializer = TagWriteRequestSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data

        comic_pks = self.resolve_comic_pks(data["collection"], data["pks"])
        if not comic_pks:
            return Response({"detail": "No comics matched."}, status=400)

        try:
            defaults = ComicboxTaggingDefaults.objects.get(pk=1)
        except ComicboxTaggingDefaults.DoesNotExist:
            defaults = None

        req_delete = data.get("delete_original")
        if req_delete is not None:
            delete_original = req_delete
        else:
            delete_original = bool(defaults and defaults.delete_original)

        req_rename = data.get("rename")
        if req_rename is not None:
            rename = req_rename
        else:
            rename = bool(defaults and defaults.rename_files)

        task = BulkTagWriteTask(
            comic_pks=comic_pks,
            patch=json.loads(data.get("patch") or "null"),
            delete_keys=tuple(data.get("delete_keys") or ()),
            mode=data["mode"],
            formats=tuple(data["formats"]),
            delete_original=delete_original,
            rename=rename,
        )
        LIBRARIAN_QUEUE.put(task)
        return Response(
            {
                "detail": f"Tag write queued for {len(comic_pks)} comics.",
                "skipped": self.skipped_read_only,
            },
            status=HTTP_202_ACCEPTED,
        )

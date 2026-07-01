"""Admin Tag Write View."""

import json
from collections.abc import Sequence
from pathlib import Path
from types import MappingProxyType
from typing import override

from comicbox.box import Comicbox
from comicbox.formats import MetadataFormats
from rest_framework.permissions import BasePermission, IsAdminUser
from rest_framework.response import Response
from rest_framework.status import HTTP_202_ACCEPTED

from codex.librarian.mp_queue import LIBRARIAN_QUEUE
from codex.librarian.onlinetag.tasks import OnlineTagByIdTask
from codex.librarian.scribe.tasks import BulkTagWriteTask
from codex.models.admin import ComicboxTaggingDefaults
from codex.models.comic import Comic
from codex.serializers.admin.tagging import (
    TagByIdRequestSerializer,
    TagWriteRequestSerializer,
)
from codex.settings import COMICBOX_CONFIG
from codex.views.admin.auth import AdminAPIView
from codex.views.admin.identifier_parse import (
    parse_identifier_input,
    parse_identifier_url,
)
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


class AdminTagByIdView(FilteredComicPksView):
    """Tag a single comic by a known Metron / Comic Vine issue id (no search)."""

    @staticmethod
    def _get_defaults() -> ComicboxTaggingDefaults | None:
        """Load the tagging-defaults singleton, or None when unset."""
        try:
            return ComicboxTaggingDefaults.objects.get(pk=1)
        except ComicboxTaggingDefaults.DoesNotExist:
            return None

    @staticmethod
    def _configured_sources(defaults: ComicboxTaggingDefaults | None) -> frozenset[str]:
        """Which online sources actually have credentials configured."""
        if not defaults:
            return frozenset()
        sources = set()
        if defaults.metron_user and defaults.metron_password:
            sources.add("metron")
        if defaults.comicvine_key:
            sources.add("comicvine")
        return frozenset(sources)

    @staticmethod
    def _write_defaults(
        defaults: ComicboxTaggingDefaults | None,
    ) -> tuple[tuple[str, ...], bool]:
        """Resolve the write formats and delete-original flag from defaults."""
        if not defaults:
            return ("COMIC_INFO",), False
        formats = tuple(defaults.default_formats) or ("COMIC_INFO",)
        return formats, bool(defaults.delete_original)

    @staticmethod
    def _parse_extra_ids(
        identifiers: list[str], primary_source: str, configured: frozenset[str]
    ) -> tuple[tuple[str, int], ...]:
        """
        Parse the entered identifiers into extra ``(source, id)`` pairs to merge.

        Keeps one id per source (the primary source excluded — it's already
        pinned), so a Metron + Comic Vine pair yields the Comic Vine entry.
        Raises ValueError on an unparseable or unconfigured-source identifier.
        """
        seen = {primary_source}
        extras: list[tuple[str, int]] = []
        for raw in identifiers:
            if not (raw or "").strip():
                continue
            src, issue_id = parse_identifier_input(raw, configured_sources=configured)
            if src in seen or src not in configured:
                continue
            seen.add(src)
            extras.append((src, issue_id))
        return tuple(extras)

    @staticmethod
    def _resolve_primary(data, configured: frozenset[str]) -> tuple[str, int]:
        """Parse the primary identifier and confirm its source is configured."""
        source, issue_id = parse_identifier_input(
            data["identifier"],
            source_hint=data.get("source") or None,
            configured_sources=configured,
        )
        if source not in configured:
            msg = f"No {source} credentials configured."
            raise ValueError(msg)
        return source, issue_id

    def _resolve_extra_ids(
        self,
        data,
        defaults: ComicboxTaggingDefaults | None,
        source: str,
        configured: frozenset[str],
    ) -> tuple[tuple[str, int], ...]:
        """Resolve the merge default and parse the extra ids to merge, if any."""
        req_merge = data.get("merge_all_sources")
        if req_merge is None:
            req_merge = bool(defaults and defaults.merge_all_sources)
        if not req_merge:
            return ()
        return self._parse_extra_ids(data.get("identifiers") or [], source, configured)

    def post(self, request):
        """Parse the identifier, resolve the comic, and enqueue an id fetch."""
        serializer = TagByIdRequestSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data

        defaults = self._get_defaults()
        configured = self._configured_sources(defaults)
        if not configured:
            return Response(
                {"detail": "No online source credentials configured."}, status=400
            )
        try:
            source, issue_id = self._resolve_primary(data, configured)
            extra_ids = self._resolve_extra_ids(data, defaults, source, configured)
        except ValueError as exc:
            return Response({"detail": str(exc)}, status=400)

        comic_pks = self.resolve_comic_pks(data["collection"], [data["pk"]])
        if len(comic_pks) != 1:
            if self.skipped_read_only:
                detail = "Comic is in a read-only library."
            else:
                detail = "No comic matched."
            return Response({"detail": detail}, status=400)
        (comic_pk,) = tuple(comic_pks)

        formats, delete_original = self._write_defaults(defaults)
        req_rename = data.get("rename")
        if req_rename is not None:
            rename = req_rename
        else:
            rename = bool(defaults and defaults.rename_files)
        task = OnlineTagByIdTask(
            comic_pk=comic_pk,
            source=source,
            issue_id=issue_id,
            formats=formats,
            delete_original=delete_original,
            rename=rename,
            extra_ids=extra_ids,
        )
        LIBRARIAN_QUEUE.put(task)
        return Response({"source": source, "id": issue_id}, status=HTTP_202_ACCEPTED)


class AdminTagWritePreflightView(FilteredComicPksView):
    """Check how many comics need conversion before writing."""

    @staticmethod
    def _preview_one(old_path: Path, metadata: dict | None) -> str:
        """
        Return the comicbox-scheme name the given patch produces for one comic.

        Overlays the pending (unsaved) patch onto the archive's metadata in
        memory and serializes the FILENAME format — the same construction
        ``rename_file`` uses — so the dialog can show the would-be name. Opens
        the archive (I/O). Returns "" when no name could be built.
        """
        try:
            with Comicbox(old_path, config=COMICBOX_CONFIG, metadata=metadata) as car:
                return car.to_string(MetadataFormats.FILENAME) or ""
        except Exception:
            return ""

    def _filename_previews(
        self, comic_pks: frozenset[int], patch_str: str
    ) -> list[dict[str, str]]:
        """Preview the rename (old → new) for each selected comic, capped."""
        patch = json.loads(patch_str or "null")
        metadata = {"comicbox": patch} if patch else None
        comics = (
            Comic.objects.filter(pk__in=comic_pks)
            .only("pk", "path")
            .order_by("pk")[:_FILENAME_PREVIEW_LIMIT]
        )
        previews: list[dict[str, str]] = []
        for comic in comics:
            old_path = Path(comic.path)
            previews.append(
                {"old": old_path.name, "new": self._preview_one(old_path, metadata)}
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
                    comic_pks, data.get("patch") or ""
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

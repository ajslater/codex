"""OPDS Progression 1.0 view."""

# https://drafts.opds.io/opds-progression-1.0.html
from http import HTTPStatus
from typing import TYPE_CHECKING, Any, override

from django.db.models import QuerySet
from django.db.models.expressions import F
from django.db.models.query_utils import FilteredRelation
from django.utils import timezone
from loguru import logger
from rest_framework.exceptions import ValidationError
from rest_framework.parsers import JSONParser
from rest_framework.renderers import JSONRenderer
from rest_framework.response import Response

from codex.librarian.bookmark.update import BookmarkUpdateMixin
from codex.models.bookmark import Bookmark
from codex.models.comic import Comic
from codex.serializers.opds.v2.progression import OPDS2ProgressionSerializer
from codex.util import max_none
from codex.views.auth import AuthFilterGenericAPIView
from codex.views.bookmark import BookmarkAuthMixin, BookmarkFilterMixin
from codex.views.const import COLLECTION_MODEL_MAP
from codex.views.exceptions import NoContent
from codex.views.opds.auth import OPDSAuthMixin
from codex.views.opds.const import MimeType
from codex.views.opds.v2.const import HrefData
from codex.views.opds.v2.href import OPDS2HrefMixin

if TYPE_CHECKING:
    from datetime import datetime

# OPDS Progression 1.0 media type.
PROGRESSION_MIME_TYPE = MimeType.PROGRESSION
# RFC 7807, which OPDS Progression 1.0 uses for error payloads.
_PROBLEM_MIME_TYPE = "application/problem+json"
_PROBLEM_INVALID_PAYLOAD = (
    HTTPStatus.BAD_REQUEST,
    "https://registry.opds.io/error#progression-invalid-payload",
    "Progression could not be updated due to an invalid payload.",
)
_PROBLEM_CONFLICT = (
    HTTPStatus.CONFLICT,
    "https://registry.opds.io/error#progression-date",
    "A more recent progression point is already available.",
)
# The draft lists no 404; this one is Codex's own.
_PROBLEM_NOT_FOUND = (
    HTTPStatus.NOT_FOUND,
    "https://github.com/ajslater/codex#progression-not-found",
    "No such publication, or not yours.",
)


class OPDSProgressionParser(JSONParser):
    """Parses an OPDS Progression Document as JSON."""

    media_type = PROGRESSION_MIME_TYPE


class OPDSProgressionRenderer(JSONRenderer):
    """Renders an OPDS Progression Document as JSON."""

    media_type = PROGRESSION_MIME_TYPE


# This is an independent api requiring a separate get.


class OPDS2ProgressionView(
    OPDSAuthMixin,
    OPDS2HrefMixin,
    BookmarkAuthMixin,
    BookmarkFilterMixin,
    AuthFilterGenericAPIView,
):
    """OPDS Progression 1.0 view."""

    parser_classes = (
        OPDSProgressionParser,
        *AuthFilterGenericAPIView.parser_classes,
    )
    renderer_classes = (  # pyright: ignore[reportIncompatibleUnannotatedOverride]
        OPDSProgressionRenderer,
        *AuthFilterGenericAPIView.renderer_classes,
    )
    serializer_class = OPDS2ProgressionSerializer
    content_type = OPDSProgressionParser.media_type

    def __init__(self, *args, **kwargs) -> None:
        """Initialize Bookmark Filter."""
        self.init_bookmark_filter()
        super().__init__(*args, **kwargs)

    @property
    def device(self) -> dict[str, str]:
        """
        Synthetic server-identity device.

        OPDS Progression 1.0 requires a ``device`` (id + name); Codex doesn't
        track per-device state, so the position is attributed to the Codex
        server itself (its base URL is a stable, valid URI).
        """
        return {"id": self.request.build_absolute_uri("/"), "name": "Codex"}

    def _progression_href(self, pk: int, page: int, page_count: int) -> str | None:
        """Build an href to the current page."""
        acq_kwargs = {"pk": pk, "page": page}
        max_page = max_none(page_count - 1, 0)
        data = HrefData(
            acq_kwargs, url_name="opds:bin:page", min_page=0, max_page=max_page
        )
        return self.href(data)

    def _document(
        self, pk: int, page: int, page_count: int, modified: "datetime"
    ) -> dict[str, Any]:
        """Build an OPDS Progression 1.0 document."""
        # ``progression`` is the overall position as a 0..1 fraction:
        # page / (page_count - 1), so the first page is 0.0 and the last 1.0.
        progression = min(page / max(page_count - 1, 1), 1.0)
        return {
            # Pages are 1-indexed for display.
            "title": f"Page {page + 1}",
            "modified": modified,
            "device": self.device,
            "progression": progression,
            "references": [self._progression_href(pk, page, page_count)],
        }

    @staticmethod
    def _problem(problem: tuple[HTTPStatus, str, str]) -> Response:
        """RFC 7807 Problem Details response."""
        status, type_uri, title = problem
        return Response(
            {"type": type_uri, "title": title},
            status=status,
            content_type=_PROBLEM_MIME_TYPE,
        )

    def _get_bookmark_query(self) -> QuerySet:
        group = self.kwargs.get("group")
        pk = self.kwargs.get("pk")

        if not (group and pk):
            reason = f"Bad primary key for {group}:{pk}"
            raise ValidationError(reason, code="422")

        model = COLLECTION_MODEL_MAP.get(group)
        if not model:
            reason = f"No model found for group {group}"
            raise ValidationError(reason, code="422")

        acl_filter = self.get_acl_filter(model, self.request.user)
        qs = model.objects.filter(acl_filter).distinct()

        bm_rel = self.get_bm_rel(model)
        bm_filter = self.get_my_bookmark_filter(bm_rel)
        return qs.annotate(
            my_bookmark=FilteredRelation("bookmark", condition=bm_filter),
            bookmark_updated_at=F("my_bookmark__updated_at"),
        )

    @override
    def get_object(self) -> dict[str, Any]:
        """Build the OPDS Progression 1.0 document."""
        pk = self.kwargs.get("pk")
        obj = (
            self._get_bookmark_query()
            .annotate(bookmark_page=F("my_bookmark__page"))
            .only("page_count")
            .get(pk=pk)
        )
        if not obj.bookmark_updated_at:
            raise NoContent
        return self._document(
            obj.pk, obj.bookmark_page or 0, obj.page_count, obj.bookmark_updated_at
        )

    def get(self, *args, **kwargs) -> Response:
        """Get Response."""
        try:
            obj = self.get_object()
            serializer = self.get_serializer(obj)
            return Response(serializer.data)
        except Comic.DoesNotExist:
            return self._problem(_PROBLEM_NOT_FOUND)
        except NoContent:
            # OPDS Progression 1.0: "no progression communicated yet" is
            # 200 with an empty payload. The draft defines no 204.
            return Response(None, status=HTTPStatus.OK)
        except Exception as exc:
            logger.error("Error in OPDS progression API")
            logger.exception(exc)
            raise

    def _get_page_count(self) -> int | None:
        """
        Get the comic's page count, or ``None`` if the caller can't write it.

        ACL-filtered: the ``None`` return becomes a 404, so an unfiltered
        lookup here turns the endpoint into an existence oracle for
        comics in libraries the caller cannot see. ``include_missing``
        keeps scanner-stamped rows writable (see :meth:`put`).
        """
        comic_pk = self.kwargs.get("pk")
        acl_filter = self.get_acl_filter(Comic, self.request.user, include_missing=True)
        return (
            Comic.objects.filter(acl_filter, pk=comic_pk)
            .values_list("page_count", flat=True)
            .first()
        )

    def put(self, *_args, **_kwargs) -> Response:
        """
        Update the bookmark from an OPDS Progression 1.0 document.

        Per the OPDS Progression spec, when the client echoes the ``modified``
        timestamp it received from the matching GET, the server must reject the
        PUT with 409 if the DB has a fresher bookmark (multi-device sync
        conflict). The conflict check is folded into a single atomic conditional
        UPDATE, and falls back to a synchronous create when no bookmark exists
        yet. The response is the stored Progression Document; errors carry an
        RFC 7807 Problem Details body.

        The library-group and age-rating ACL applies, via
        :meth:`_get_page_count` -- a comic the caller cannot browse
        is a 404 here too, rather than an existence oracle. Only the
        pending-delete half is deliberately relaxed, so the write still
        lands on a scanner-stamped comic: writes land, reads hide. Note
        the asymmetry that creates and accept it -- the GET above hides
        stamped rows, so during a retention window a client can write a
        position it cannot read back. That beats silently discarding it.
        """
        serializer = self.get_serializer(data=self.request.data, partial=True)
        if not serializer.is_valid():
            return self._problem(_PROBLEM_INVALID_PAYLOAD)
        data = serializer.validated_data

        progression: float | None = data.get("progression")
        if progression is None:
            return self._problem(_PROBLEM_INVALID_PAYLOAD)
        page_count = self._get_page_count()
        if page_count is None:
            return self._problem(_PROBLEM_NOT_FOUND)
        page = round(progression * max(page_count - 1, 0))

        auth_filter = self.get_bookmark_auth_filter()
        comic_pk = self.kwargs["pk"]
        bookmark_filter = {**auth_filter, "comic_id": comic_pk}
        updated = 0
        if (new_modified := data.get("modified")) is not None:
            # Atomic conditional UPDATE: succeeds only when the existing
            # bookmark's ``updated_at`` is at-or-before the client's echo.
            updated = Bookmark.objects.filter(
                **bookmark_filter, updated_at__lte=new_modified
            ).update(page=page, updated_at=timezone.now())
            if not updated and Bookmark.objects.filter(**bookmark_filter).exists():
                # A fresher bookmark exists: a real conflict.
                return self._problem(_PROBLEM_CONFLICT)
        if not updated:
            # First write, or no ``modified`` echoed (a liberal accept).
            # Written in-request rather than queued so the ``modified``
            # returned below is the stored one: a client that echoes it
            # on its next PUT must not get a spurious 409.
            BookmarkUpdateMixin.update_bookmarks(
                auth_filter, (comic_pk,), {"page": page}
            )

        stored_page, modified = (
            Bookmark.objects.filter(**bookmark_filter)
            .values_list("page", "updated_at")
            .get()
        )
        document = self._document(comic_pk, stored_page or 0, page_count, modified)
        return Response(self.get_serializer(document).data)

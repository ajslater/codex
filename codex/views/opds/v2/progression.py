"""OPDS Progression 1.0 view."""

# https://drafts.opds.io/opds-progression-1.0.html
from http import HTTPStatus
from typing import TYPE_CHECKING, Any, override

from django.db.models import QuerySet
from django.db.models.expressions import F, Value
from django.db.models.fields import FloatField
from django.db.models.functions.comparison import Cast, Coalesce, Greatest, Least
from django.db.models.query_utils import FilteredRelation
from django.utils import timezone
from loguru import logger
from rest_framework.exceptions import ValidationError
from rest_framework.parsers import JSONParser
from rest_framework.renderers import JSONRenderer
from rest_framework.response import Response

from codex.models.bookmark import Bookmark
from codex.models.comic import Comic
from codex.serializers.opds.v2.progression import OPDS2ProgressionSerializer
from codex.util import max_none
from codex.views.auth import AuthFilterGenericAPIView
from codex.views.bookmark import BookmarkFilterMixin, BookmarkPageMixin
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
    BookmarkPageMixin,
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

    # Annotated queryset rows carry ``bookmark_updated_at`` /
    # ``page`` / ``progress`` synthetic columns the type system
    # can't see on ``Comic``. The real model attribute
    # ``page_count`` is also accessed. Type as ``Any`` to keep
    # the queryset-aliased reads honest; the queryset itself is
    # built by ``_get_bookmark_query`` and reassigned in
    # ``get_object``.
    _obj: Any

    def __init__(self, *args, **kwargs) -> None:
        """Initialize Bookmark Filter."""
        self.init_bookmark_filter()
        super().__init__(*args, **kwargs)
        self._obj = Comic()

    @property
    def modified(self):
        """Get modified from bookmark."""
        return self._obj.bookmark_updated_at

    @property
    def device(self) -> dict[str, str]:
        """
        Synthetic server-identity device.

        OPDS Progression 1.0 requires a ``device`` (id + name); Codex doesn't
        track per-device state, so the position is attributed to the Codex
        server itself (its base URL is a stable, valid URI).
        """
        return {"id": self.request.build_absolute_uri("/"), "name": "Codex"}

    @property
    def title(self) -> str:
        """Human-readable position; pages are 1-indexed for display."""
        return f"Page {self._obj.page + 1}"

    @property
    def _progression_href(self):
        """Build an href to the current page."""
        acq_kwargs = {
            "pk": self._obj.pk,
            "page": self._obj.page,
        }
        max_page = max_none(self._obj.page_count - 1, 0)
        data = HrefData(
            acq_kwargs, url_name="opds:bin:page", min_page=0, max_page=max_page
        )
        return self.href(data)

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
        qs = self._get_bookmark_query()
        # ``progression`` is the overall position as a 0..1 fraction:
        # page / (page_count - 1), so the first page is 0.0 and the last 1.0.
        progress = Least(
            F("page") / Greatest(Cast(F("page_count") - 1, FloatField()), 1.0),
            Value(1.0),
        )
        qs = (
            qs.annotate(
                page=Coalesce(F("my_bookmark__page"), 0),
                progress=progress,
            )
            .only("page_count")
            .distinct()
        )
        self._obj = qs.get(pk=pk)

        if not self._obj.bookmark_updated_at:
            raise NoContent

        return {
            "title": self.title,
            "modified": self.modified,
            "device": self.device,
            "progression": self._obj.progress,
            "references": [self._progression_href],
        }

    def get(self, *args, **kwargs) -> Response:
        """Get Response."""
        try:
            obj = self.get_object()
            serializer = self.get_serializer(obj)
            return Response(serializer.data)
        except Comic.DoesNotExist:
            return Response(status=HTTPStatus.NOT_FOUND)
        except NoContent:
            return Response(status=HTTPStatus.NO_CONTENT)
        except Exception as exc:
            logger.error("Error in OPDS progression API")
            logger.exception(exc)
            raise

    def _progression_to_page(self, progression: float) -> int | None:
        """Convert a 0..1 ``progression`` fraction to a 0-indexed page."""
        comic_pk = self.kwargs.get("pk")
        page_count = (
            Comic.objects.filter(pk=comic_pk)
            .values_list("page_count", flat=True)
            .first()
        )
        if page_count is None:
            return None
        return round(progression * max(page_count - 1, 0))

    def put(self, *_args, **_kwargs) -> Response:
        """
        Update the bookmark from an OPDS Progression 1.0 document.

        Per the OPDS Progression spec, when the client echoes the ``modified``
        timestamp it received from the matching GET, the server must reject the
        PUT with 409 if the DB has a fresher bookmark (multi-device sync
        conflict). The conflict check is folded into a single atomic conditional
        UPDATE, and falls back to the async ``update_bookmark`` path when no
        existing bookmark matches (first-time write or no ``modified`` echo).
        """
        data = self.request.data
        serializer = self.get_serializer(data=data, partial=True)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data

        progression: float | None = data.get("progression")
        if progression is None:
            return Response(status=HTTPStatus.BAD_REQUEST)
        page = self._progression_to_page(progression)
        if page is None:
            return Response(status=HTTPStatus.NOT_FOUND)
        self.kwargs["page"] = page

        new_modified: datetime | None = data.get("modified")
        if new_modified is None:
            # No timestamp echoed — liberal accept (matches the prior
            # ``Update anyway on missing modified`` behavior).
            self.update_bookmark()
            return Response(status=HTTPStatus.OK)

        # Atomic conditional UPDATE: succeeds only when the existing
        # bookmark's ``updated_at`` is at-or-before the client's echo.
        auth_filter = self.get_bookmark_auth_filter()
        comic_pk = self.kwargs.get("pk")
        bookmark_filter = {**auth_filter, "comic_id": comic_pk}
        updated_count = Bookmark.objects.filter(
            **bookmark_filter, updated_at__lte=new_modified
        ).update(page=page, updated_at=timezone.now())
        if updated_count:
            return Response(status=HTTPStatus.OK)

        # No row matched. Either (a) no bookmark exists yet — fall
        # through to the async create via ``update_bookmark``, or (b) a
        # bookmark exists but its ``updated_at`` is fresher than the
        # client's echo → real conflict.
        if Bookmark.objects.filter(**bookmark_filter).exists():
            return Response(status=HTTPStatus.CONFLICT)
        self.update_bookmark()
        return Response(status=HTTPStatus.OK)

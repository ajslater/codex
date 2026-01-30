"""OPDS 2 Progression view."""
# https://github.com/opds-community/drafts/discussions/67#discussioncomment-6414507

from http import HTTPStatus
from types import MappingProxyType
from typing import TYPE_CHECKING

from dateparser import parse
from django.db.models import QuerySet
from django.db.models.expressions import F, Value
from django.db.models.fields import FloatField
from django.db.models.functions.comparison import Cast, Coalesce, Greatest, Least
from django.db.models.query_utils import FilteredRelation
from django.http import HttpResponse
from loguru import logger
from rest_framework.exceptions import ValidationError
from rest_framework.parsers import JSONParser
from rest_framework.response import Response
from typing_extensions import override

from codex.models.comic import Comic
from codex.serializers.opds.v2.progression import OPDS2ProgressionSerializer
from codex.util import max_none
from codex.views.auth import AuthFilterGenericAPIView
from codex.views.bookmark import BookmarkFilterMixin, BookmarkPageMixin
from codex.views.const import GROUP_MODEL_MAP
from codex.views.opds.auth import OPDSAuthMixin
from codex.views.opds.v2.const import HrefData
from codex.views.opds.v2.href import OPDS2HrefMixin

if TYPE_CHECKING:
    from codex.models.groups import BrowserGroupModel

_EMPTY_DEVICE = MappingProxyType(
    {
        "id": "",
        "name": "",
    }
)


class ReadiumProgressionParser(JSONParser):
    """Parses 'application/vnd.readium.progression+json' as standard JSON."""

    media_type = "application/vnd.readium.progression+json"


# This is an independent api requiring a separate get.
class OPDS2ProgressionView(
    OPDSAuthMixin,
    OPDS2HrefMixin,
    BookmarkPageMixin,
    BookmarkFilterMixin,
    AuthFilterGenericAPIView,
):
    """OPDS 2 Progression view."""

    parser_classes = (ReadiumProgressionParser, JSONParser)
    serializer_class = OPDS2ProgressionSerializer

    def __init__(self, *args, **kwargs):
        """Initialize Bookmark Filter."""
        self.init_bookmark_filter()
        super().__init__(*args, **kwargs)
        self._obj: BrowserGroupModel = Comic()
        self._user_agent_name: str | None = None

    @property
    def modified(self):
        """Get modified from bookmark."""
        return self._obj.bookmark_updated_at  # pyright: ignore[reportAttributeAccessIssue], #ty: ignore[unresolved-attribute]

    @property
    def device(self):
        """Dummy device."""
        # Codex doesn't device for progression.
        return _EMPTY_DEVICE

    @property
    def title(self):
        """The locator title is the page number."""
        return f"Page {self._obj.page}"  # pyright: ignore[reportAttributeAccessIssue], #ty: ignore[unresolved-attribute]

    @property
    def _progression_href(self):
        """Build a Progression HRef."""
        acq_kwargs = {
            "pk": self._obj.pk,
            "page": self._obj.page,  # pyright: ignore[reportAttributeAccessIssue],  #ty: ignore[unresolved-attribute]
        }
        max_page = max_none(self._obj.page_count - 1, 0)  # pyright: ignore[reportAttributeAccessIssue], #ty: ignore[unresolved-attribute]
        data = HrefData(
            acq_kwargs, url_name="opds:bin:page", min_page=0, max_page=max_page
        )
        return self.href(data)

    @property
    def _locations(self):
        """Build the Locations object."""
        return {
            "position": self._obj.page,  # pyright: ignore[reportAttributeAccessIssue], # ty: ignore[unresolved-attribute]
            "progression": self._obj.progress,  # pyright: ignore[reportAttributeAccessIssue], # ty: ignore[unresolved-attribute]
            "total_progression": self._obj.progress,  # pyright: ignore[reportAttributeAccessIssue], # ty: ignore[unresolved-attribute]
        }

    @property
    def locator(self):
        """Build the Locator object."""
        return {
            "title": self.title,  # See publication.py:103
            "href": self._progression_href,
            "type": "image/jpeg",
            "locations": self._locations,
        }

    def _get_bookmark_query(self) -> QuerySet:
        group = self.kwargs.get("group")
        pk = self.kwargs.get("pk")

        if not (group and pk):
            reason = f"Bad primary key for {group}:{pk}"
            raise ValidationError(reason, code="422")

        model = GROUP_MODEL_MAP.get(group)
        if not model:
            reason = f"No model found for group {group}"
            raise ValidationError(reason, code="422")

        acl_filter = self.get_group_acl_filter(model, self.request.user)
        qs = model.objects.filter(acl_filter).distinct()

        bm_rel = self.get_bm_rel(model)
        bm_filter = self.get_my_bookmark_filter(bm_rel)
        return qs.annotate(
            my_bookmark=FilteredRelation("bookmark", condition=bm_filter),
            bookmark_updated_at=F("my_bookmark__updated_at"),
        )

    @override
    def get_object(self):
        """Build the progression data object."""
        qs = self._get_bookmark_query()
        progress = Least(
            F("page") / Greatest(Cast(F("page_count"), FloatField()), 1.0), Value(1.0)
        )
        qs = qs.annotate(
            page=Coalesce(F("my_bookmark__page"), 0),
            progress=progress,
        )
        pk = self.kwargs.get("pk")
        self._obj = qs.only("page_count").distinct().get(pk=pk)

        if not self._obj.bookmark_updated_at:  # pyright: ignore[reportAttributeAccessIssue]
            HttpResponse(status=204)

        return {
            "modified": self.modified,
            "device": self.device,
            "locator": self.locator,
        }

    def get(self, *args, **kwargs):
        """Get Response."""
        try:
            obj = self.get_object()
            serializer = self.get_serializer(obj)
            return Response(
                serializer.data
                # , content_type=ReadiumProgressionParser.media_type
            )
        except Exception:
            logger.exception("progression")
            raise

    def put(self, *_args, **_kwargs):
        """Update the bookmark."""
        data = self.request.data
        serializer = self.get_serializer(data=data, partial=True)
        serializer.is_valid(raise_exception=True)

        data = serializer.validated_data
        conflict = False
        status_code = HTTPStatus.BAD_REQUEST
        if new_modified_str := data.get("modified"):
            new_modified = parse(new_modified_str)
            qs = self._get_bookmark_query()
            comic = qs.first()
            conflict = comic and comic.bookmark_updated_at > new_modified

        # Update anyway on missing modified. Liberal acceptance, not according to spec.
        if conflict:
            status_code = HTTPStatus.CONFLICT
        else:
            position: int | None = (
                data.get("locator", {}).get("locations", {}).get("position")
            )
            if position is not None:
                self.kwargs["page"] = position
                self.update_bookmark()
                status_code = HTTPStatus.OK
        return Response(status=status_code)

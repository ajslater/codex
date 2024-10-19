"""OPDS 2 Progression view."""
# https://github.com/opds-community/drafts/discussions/67#discussioncomment-6414507

from types import MappingProxyType

from django.db.models.expressions import F, Value
from django.db.models.fields import FloatField
from django.db.models.functions.comparison import Cast, Coalesce, Greatest, Least
from django.db.models.query_utils import FilteredRelation
from rest_framework.exceptions import ValidationError
from rest_framework.response import Response

from codex.logger.logging import get_logger
from codex.serializers.opds.v2.progression import OPDS2ProgressionSerializer
from codex.util import max_none
from codex.views.auth import AuthFilterGenericAPIView
from codex.views.bookmark import BookmarkFilterMixin, BookmarkPageView
from codex.views.const import GROUP_MODEL_MAP
from codex.views.opds.v2.href import HrefData, OPDS2HrefMixin

_EMPTY_DEVICE = MappingProxyType(
    {
        "id": "",
        "name": "",
    }
)
LOG = get_logger(__name__)


# This is an independent api requiring a separate get.
class OPDS2ProgressionView(
    BookmarkFilterMixin, OPDS2HrefMixin, BookmarkPageView, AuthFilterGenericAPIView
):
    """OPDS 2 Progression view."""

    serializer_class = OPDS2ProgressionSerializer

    @property
    def modified(self):
        """Get modified from bookmark."""
        return self._obj.bookmark_updated_at  # type: ignore

    @property
    def device(self):
        """Dummy device."""
        # Codex doesn't record this.
        return _EMPTY_DEVICE

    @property
    def title(self):
        """The locator title is the page number."""
        return f"Page {self._obj.page}"  # type: ignore

    @property
    def _progression_href(self):
        """Build a Progression HRef."""
        acq_kwargs = {
            "pk": self._obj.pk,
            "page": self._obj.page,  # type: ignore
        }
        max_page = max_none(self._obj.page_count - 1, 0)  # type: ignore
        data = HrefData(
            acq_kwargs,
            url_name="opds:bin:page",
            min_page=0,
            max_page=max_page,  # type: ignore
            # absolute_query_params=True,
        )
        return self.href(data)

    @property
    def _locations(self):
        """Build the Locations object."""
        return {
            "position": self._obj.page,  # type: ignore
            "progression": self._obj.progress,  # type: ignore
            "total_progression": self._obj.progress,  # type: ignore
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

    def get_object(self):
        """Build the progression data object."""
        group = self.kwargs.get("group")
        pk = self.kwargs.get("pk")

        if not pk:
            reason = f"Bad primary key for {group}:{pk}"
            return ValidationError(reason, code="422")

        model = GROUP_MODEL_MAP.get(group)
        if not model:
            reason = f"No model found for group {group}"
            raise ValidationError(reason, code="422")

        acl_filter = self.get_group_acl_filter(model, self.request.user)
        qs = model.objects.filter(acl_filter).distinct()

        bm_rel = self.get_bm_rel(model)
        bm_filter = self.get_my_bookmark_filter(bm_rel)
        progress = Least(
            F("page") / Greatest(Cast(F("page_count"), FloatField()), 1.0), Value(1.0)
        )

        qs = qs.annotate(
            my_bookmark=FilteredRelation("bookmark", condition=bm_filter),
            bookmark_updated_at=F("my_bookmark__updated_at"),
            page=Coalesce(F("my_bookmark__page"), 0),
            progress=progress,
        )
        self._obj = qs.only("page_count").distinct().get(pk=pk)

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
            return Response(serializer.data)
        except Exception:
            LOG.exception("progression")
            raise

    # PUT handled by BookmarkPageView parent

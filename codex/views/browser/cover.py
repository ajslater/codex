"""Comic cover thumbnail view."""

from django.db import OperationalError
from django.db.models.query import Q
from django.http.response import StreamingHttpResponse
from drf_spectacular.types import OpenApiTypes
from drf_spectacular.utils import extend_schema
from rest_framework.renderers import BaseRenderer

from codex.librarian.covers.create import CoverCreateThread
from codex.librarian.covers.path import CoverPathMixin
from codex.librarian.mp_queue import LIBRARIAN_QUEUE
from codex.logger.logging import get_logger
from codex.models import Comic, Volume
from codex.models.groups import Folder
from codex.models.paths import CustomCover
from codex.serializers.browser.settings import BrowserCoverInputSerializer
from codex.views.browser.annotate.order import BrowserAnnotateOrderView
from codex.views.const import (
    CUSTOM_COVER_GROUP_RELATION,
    GROUP_RELATION,
    MISSING_COVER_FN,
    MISSING_COVER_NAME_MAP,
    STATIC_IMG_PATH,
)
from codex.views.util import chunker

LOG = get_logger(__name__)


class WEBPRenderer(BaseRenderer):
    """Render WEBP images."""

    media_type = "image/webp"
    format = "webp"
    charset = None
    render_style = "binary"

    def render(self, data, *_args, **_kwargs):
        """Return raw data."""
        return data


class CoverView(BrowserAnnotateOrderView):
    """ComicCover View."""

    input_serializer_class = BrowserCoverInputSerializer
    renderer_classes = (WEBPRenderer,)
    content_type = "image/webp"
    TARGET = "cover"
    REPARSE_JSON_FIELDS = frozenset(
        BrowserAnnotateOrderView.REPARSE_JSON_FIELDS | {"parent"}
    )

    def get_group_filter(self, group=None, pks=None, page_mtime=False):
        """Get group filter for First Cover View."""
        if self.params.get("dynamic_covers") or self.model in (Volume, Folder):
            return super().get_group_filter(group=group, pks=pks, page_mtime=page_mtime)

        # First cover group filter relies on sort names to look outside the browser supplied pks
        # For multi_groups not in the browser query.
        pks = self.kwargs["pks"]
        qs = self.model.objects.filter(pk__in=pks)  # type: ignore
        sort_names = qs.values_list("sort_name", flat=True).distinct()
        model_rel = GROUP_RELATION[self.model_group]
        group_filter = {f"{model_rel}__sort_name__in": sort_names}

        parent = self.params.get("parent", {})
        if parent_pks := parent.get("pks"):
            parent_rel = GROUP_RELATION[parent["group"]]
            group_filter[f"{parent_rel}__pk__in"] = parent_pks
        return Q(**group_filter)

    def _get_comic_cover(self):
        pks = self.kwargs["pks"]
        return pks[0], False

    def _get_custom_cover(self):
        """Get Custom Cover."""
        if self.model is Volume or not self.params.get("custom_covers"):
            return None
        group = self.kwargs["group"]
        group_rel = CUSTOM_COVER_GROUP_RELATION[group]
        pks = self.kwargs["pks"]
        comic_filter = {f"{group_rel}__in": pks}
        qs = CustomCover.objects.filter(**comic_filter)
        qs = qs.only("pk")
        return qs.first()

    def _get_dynamic_cover(self):
        """Get dynamic cover."""
        comic_qs = self.get_filtered_queryset(Comic)
        comic_qs = self.annotate_order_aggregates(comic_qs)
        comic_qs = self.add_order_by(comic_qs)
        comic_qs = comic_qs.only("pk")
        comic = comic_qs.first()
        cover_pk = comic.pk if comic else 0
        return cover_pk, False

    def _get_cover_pk(self) -> tuple[int, bool]:
        """Get Cover Pk queryset for comic queryset."""
        if self.model is Comic:
            cover_pk, custom = self._get_comic_cover()
        elif custom_cover := self._get_custom_cover():
            cover_pk = custom_cover.pk
            custom = True
        else:
            cover_pk, custom = self._get_dynamic_cover()
        return cover_pk, custom

    def _get_missing_cover_path(self):
        """Get the missing cover, which is a default svg if fetched for a group."""
        group: str = self.kwargs["group"]
        cover_name = MISSING_COVER_NAME_MAP.get(group)
        if cover_name:
            cover_fn = cover_name + ".svg"
            content_type = "image/svg+xml"
        else:
            cover_fn = MISSING_COVER_FN
            content_type = "image/webp"
        cover_path = STATIC_IMG_PATH / cover_fn
        return cover_path, content_type

    def _get_cover_data(self, pk, custom):
        thumb_buffer = None
        content_type = "image/webp"

        cover_path = CoverPathMixin.get_cover_path(pk, custom)
        if not cover_path.exists():
            thumb_buffer = CoverCreateThread.create_cover_from_path(
                pk, cover_path, LOG, LIBRARIAN_QUEUE, custom
            )
            if not thumb_buffer:
                cover_path, content_type = self._get_missing_cover_path()
        elif cover_path.stat().st_size == 0:
            cover_path, content_type = self._get_missing_cover_path()

        cover_file = thumb_buffer if thumb_buffer else cover_path.open("rb")
        return cover_file, content_type

    @extend_schema(
        parameters=[BrowserAnnotateOrderView.input_serializer_class],
        responses={(200, content_type): OpenApiTypes.BINARY},
    )
    def get(self, *args, **kwargs):  # type: ignore
        """Get comic cover."""
        try:
            try:
                pk, custom = self._get_cover_pk()
            except OperationalError as exc:
                self._handle_operational_error(exc)
                pk = 0
                custom = False
            cover_file, content_type = self._get_cover_data(pk, custom)
            return StreamingHttpResponse(chunker(cover_file), content_type=content_type)
        except Exception:
            LOG.exception("Get cover")

"""Comic cover thumbnail view."""

from django.http import HttpResponse
from drf_spectacular.types import OpenApiTypes
from drf_spectacular.utils import extend_schema
from rest_framework.renderers import BaseRenderer

from codex.librarian.covers.create import CoverCreateMixin
from codex.librarian.covers.path import CoverPathMixin
from codex.librarian.mp_queue import LIBRARIAN_QUEUE
from codex.logger.logging import get_logger
from codex.models import Comic, Folder, Volume
from codex.models.paths import CustomCover
from codex.serializers.choices import DEFAULTS
from codex.views.browser.annotations import BrowserAnnotationsView
from codex.views.const import (
    GROUP_RELATION,
    MISSING_COVER_FN,
    MISSING_COVER_NAME_MAP,
    STATIC_IMG_PATH,
)

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


class CoverView(BrowserAnnotationsView):
    """ComicCover View."""

    renderer_classes = (WEBPRenderer,)
    content_type = "image/webp"

    def get_model_group(self):
        """Return the url group."""
        return self.kwargs["group"]

    def init_request(self):
        """Initialize request."""
        self.parse_params()
        self.set_model()

    def _get_comic_cover(self):
        pks = self.kwargs["pks"]
        return pks[0], False

    def _use_dynamic_cover(self):
        if not self.params.get("dynamic_covers"):
            return False
        filters = self.params.get("filters", {})
        for key, value in filters.items():
            if key == "bookmark" and value != DEFAULTS["bookmarkFilter"]:
                return True
            if value:
                return True

        order_by = self.params.get("order_by")
        default_order_by = "filename" if self.model == Folder else "sort_name"
        if order_by != default_order_by:
            return True

        if self.params.get("order_reverse"):
            return True

        return False

    def _get_dynamic_cover(self):
        """Get dynamic cover."""
        self.set_order_key()
        pks = self.kwargs["pks"]

        if self.model != Volume and self.params.get("custom_covers"):
            group = self.kwargs["group"]
            group_rel = "folder" if self.model == Folder else GROUP_RELATION[group]  # type: ignore
            comic_filter = {f"{group_rel}__in": pks}
            custom_cover = CustomCover.objects.filter(**comic_filter).only("pk").first()
            if custom_cover:
                return custom_cover.pk, True

        comic_qs = self.get_filtered_queryset(Comic, search_binary_filter=False)
        comic_qs = self.annotate_order_aggregates(comic_qs, Comic)
        comic_qs = self.add_order_by(comic_qs, Comic)
        comic_qs = comic_qs.only("pk")
        group_by = self.get_group_by(Comic)
        comic_qs.group_by(group_by)
        comic = comic_qs.first()
        cover_pk = comic.pk if comic else 0
        return cover_pk, False

    def _get_first_cover(self):
        """Get first cover."""
        pks = self.kwargs["pks"]
        custom_covers = self.params.get("custom_covers")
        order_by = "path" if self.model == Folder else "sort_name"
        group_qs = self.model.objects.filter(pk__in=pks)  # type: ignore
        group_qs = group_qs.order_by(order_by)
        select_related = ["first_comic"]
        if custom_covers:
            select_related.append("custom_cover")
        group_qs = group_qs.select_related(*select_related)
        group_qs = group_qs.group_by("id")  # type: ignore
        group_obj = group_qs.first()
        if custom_covers and self.model != Volume and group_obj.custom_cover:
            return group_obj.custom_cover.pk, True
        cover_pk = (
            group_obj.first_comic.pk if group_obj and group_obj.first_comic else 0
        )
        return cover_pk, False

    def _get_cover_pk(self) -> tuple[int, bool]:
        """Get Cover Pk queryset for comic queryset."""
        if self.model == Comic:
            cover_pk, custom = self._get_comic_cover()
        elif self._use_dynamic_cover():
            cover_pk, custom = self._get_dynamic_cover()
        else:
            cover_pk, custom = self._get_first_cover()
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
        thumb_image_data = None
        content_type = "image/webp"

        cover_path = CoverPathMixin.get_cover_path(pk, custom)
        if not cover_path.exists():
            thumb_image_data = CoverCreateMixin.create_cover_from_path(
                pk, cover_path, LOG, LIBRARIAN_QUEUE, custom
            )
            if not thumb_image_data:
                cover_path, content_type = self._get_missing_cover_path()
        elif cover_path.stat().st_size == 0:
            cover_path, content_type = self._get_missing_cover_path()

        if not thumb_image_data:
            # if not thumb_image_data:
            with cover_path.open("rb") as f:
                thumb_image_data = f.read()
        return thumb_image_data, content_type

    @extend_schema(responses={(200, content_type): OpenApiTypes.BINARY})
    def get(self, *args, **kwargs):  # type: ignore
        """Get comic cover."""
        self.init_request()
        pk, custom = self._get_cover_pk()
        thumb_image_data, content_type = self._get_cover_data(pk, custom)
        return HttpResponse(thumb_image_data, content_type=content_type)

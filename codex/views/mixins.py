"""Cross view annotation methods."""

from django.db.models.expressions import F
from rest_framework.views import APIView

from codex.logger.logging import get_logger
from codex.models.comic import Comic, Imprint, Volume
from codex.views.const import GROUP_NAME_MAP

LOG = get_logger(__name__)
_SHOW_GROUPS = tuple(GROUP_NAME_MAP.keys())


class SharedAnnotationsMixin:
    """Cross view annotation methods."""

    @staticmethod
    def _get_order_groups(model_group, pks):
        """Annotate sort_name."""
        if not pks or len(pks) > 1:
            order_groups = _SHOW_GROUPS
        elif model_group == "c":
            order_groups = ()
        else:
            for index, nav_group in enumerate(_SHOW_GROUPS):
                if nav_group == model_group:
                    order_groups = _SHOW_GROUPS[index + 1 :]
                    break
            else:
                order_groups = _SHOW_GROUPS
        return order_groups

    @classmethod
    def get_sort_name_annotations(cls, model, model_group, pks, show):
        """Annotate sort names for browser subclasses and reader."""
        sort_name_annotations = {}
        if model is Comic:
            order_groups = cls._get_order_groups(model_group, pks)
            for order_group in order_groups:
                if show and not show.get(order_group):
                    continue
                group_name = GROUP_NAME_MAP[order_group]
                ann_name = f"{group_name}_sort_name"
                name_field = "name" if group_name == "volume" else "sort_name"
                sort_name = F(f"{group_name}__{name_field}")
                sort_name_annotations[ann_name] = sort_name
        elif model is Volume:
            sort_name_annotations["sort_name"] = F("name")
        return sort_name_annotations

    @classmethod
    def annotate_group_names(cls, qs):
        """Annotate name fields by hoisting them up."""
        # Optimized to only lookup what is used on the frontend
        target = cls.TARGET  # type: ignore
        if target not in frozenset({"browser", "opds1", "opds2", "reader"}):
            return qs
        group_names = {}
        if qs.model is Comic:
            if target != "reader":
                group_names["publisher_name"] = F("publisher__name")
                if target == "opds2":
                    group_names["imprint_name"] = F("imprint__name")
            group_names.update(
                {
                    "series_name": F("series__name"),
                    "volume_name": F("volume__name"),
                }
            )
        elif qs.model is Volume:
            group_names["series_name"] = F("series__name")
        elif qs.model is Imprint:
            group_names["publisher_name"] = F("publisher__name")
        return qs.annotate(**group_names)


class BookmarkAuthMixin(APIView):
    """Base class for Bookmark Views."""

    def get_bookmark_auth_filter(self):
        """Filter only the user's bookmarks."""
        if self.request.user.is_authenticated:
            key = "user_id"
            value = self.request.user.pk
        else:
            if not self.request.session or not self.request.session.session_key:
                LOG.debug("no session, make one")
                self.request.session.save()
            key = "session_id"
            value = self.request.session.session_key
        return {key: value}

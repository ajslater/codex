"""Cross view annotation methods."""

from typing import TYPE_CHECKING

from django.db.models import CharField
from django.db.models.expressions import Case, F, Value, When
from django.db.models.functions import Concat

from codex.librarian.bookmark.tasks import UserActiveTask
from codex.librarian.mp_queue import LIBRARIAN_QUEUE
from codex.models.comic import Comic
from codex.models.groups import Imprint, Volume
from codex.views.const import GROUP_NAME_MAP

if TYPE_CHECKING:
    from rest_framework.request import Request

_SHOW_GROUPS = tuple(GROUP_NAME_MAP.keys())
_GROUP_NAME_TARGETS = frozenset({"browser", "opds1", "opds2", "reader"})
_VARIABLE_SHOW = "pi"


class SharedAnnotationsMixin:  # (BrowserFilterView):
    """Cross view annotation methods."""

    @staticmethod
    def _get_order_group(nav_group, show, parent_group, index, pks, order_groups):
        do_break = False
        if (
            nav_group not in _VARIABLE_SHOW or show.get(nav_group)
        ) and nav_group == parent_group:
            watermark = index
            if pks and len(pks) == 1:
                watermark += 1
            order_groups = _SHOW_GROUPS[watermark:]
            do_break = True
        return order_groups, do_break

    @classmethod
    def _get_order_groups(cls, parent_group, pks, show):
        """Annotate sort_name."""
        order_groups = ()
        if parent_group != "c":
            for index, nav_group in enumerate(_SHOW_GROUPS):
                order_groups, do_break = cls._get_order_group(
                    nav_group, show, parent_group, index, pks, order_groups
                )
                if do_break:
                    break
            else:
                order_groups = _SHOW_GROUPS
        return order_groups

    @classmethod
    def get_sort_name_annotations(cls, model, parent_group, pks, show):
        """Annotate sort names for browser subclasses and reader."""
        sort_name_annotations = {}
        if model is Comic:
            order_groups = cls._get_order_groups(parent_group, pks, show)
            for order_group in order_groups:
                group_name = GROUP_NAME_MAP[order_group]
                ann_name = f"{group_name}_sort_name"
                name_field = "name" if group_name == "volume" else "sort_name"
                sort_name = F(f"{group_name}__{name_field}")
                sort_name_annotations[ann_name] = sort_name
        elif model is Volume:
            sort_name_annotations["sort_name"] = F("name")
        return sort_name_annotations

    @staticmethod
    def _volume_name_annotation(model):
        prefix = "volume__" if model is Comic else ""
        name_rel = prefix + "name"
        number_to_rel = prefix + "number_to"

        return Case(
            When(**{f"{number_to_rel}__isnull": True}, then=F(name_rel)),
            default=Concat(
                F(name_rel),
                Value("-"),
                F(number_to_rel),
            ),
            output_field=CharField(),
        )

    @classmethod
    def annotate_group_names(cls, qs):
        """Annotate name fields by hoisting them up."""
        # Optimized to only lookup what is used on the frontend
        target = cls.TARGET  #  pyright: ignore[reportAttributeAccessIssue], # ty: ignore[unresolved-attribute]
        if target not in _GROUP_NAME_TARGETS:
            return qs
        group_names = {}
        if qs.model in (Comic, Volume):
            group_names["series_name"] = F("series__name")
        if qs.model is Comic:
            if target != "reader":
                group_names["publisher_name"] = F("publisher__name")
                if target == "opds2":
                    group_names["imprint_name"] = F("imprint__name")
            group_names.update(
                {
                    "volume_name": F("volume__name"),
                    "volume_number_to": F("volume__number_to"),
                }
            )
        elif qs.model is Imprint:
            group_names["publisher_name"] = F("publisher__name")
        return qs.annotate(**group_names)


class UserActiveMixin:
    """View that records user activity."""

    def mark_user_active(self):
        """Get the app index page."""
        if TYPE_CHECKING:
            self.request: Request  # pyright: ignore[reportUninitializedInstanceVariable]
        if self.request.user and self.request.user.pk:
            task = UserActiveTask(pk=self.request.user.pk)
            LIBRARIAN_QUEUE.put(task)

"""Cross view annotation methods."""

from typing import TYPE_CHECKING

from django.db.models import CharField
from django.db.models.expressions import Case, F, Value, When
from django.db.models.functions import Concat

from codex.librarian.bookmark.tasks import UserActiveTask
from codex.librarian.mp_queue import LIBRARIAN_QUEUE
from codex.models.collections import Imprint, Volume
from codex.models.comic import Comic
from codex.views.const import COLLECTION_NAME_MAP, COMIC_COLLECTION

if TYPE_CHECKING:
    from rest_framework.request import Request

_SHOW_COLLECTIONS = tuple(COLLECTION_NAME_MAP.keys())
_COLLECTION_NAME_TARGETS = frozenset({"browser", "opds1", "opds2", "reader"})
_VARIABLE_SHOW = "pi"


class SharedAnnotationsMixin:  # (BrowserFilterView):
    """Cross view annotation methods."""

    @staticmethod
    def _get_order_collection(
        nav_collection, show, parent_collection, index, pks, order_collections
    ) -> tuple:
        do_break = False
        if (
            nav_collection not in _VARIABLE_SHOW or show.get(nav_collection)
        ) and nav_collection == parent_collection:
            watermark = index
            if pks and len(pks) == 1:
                watermark += 1
            order_collections = _SHOW_COLLECTIONS[watermark:]
            do_break = True
        return order_collections, do_break

    @classmethod
    def _get_order_collections(cls, parent_collection, pks, show) -> tuple:
        """Annotate sort_name."""
        order_collections = ()
        if parent_collection != COMIC_COLLECTION:
            for index, nav_collection in enumerate(_SHOW_COLLECTIONS):
                order_collections, do_break = cls._get_order_collection(
                    nav_collection, show, parent_collection, index, pks, order_collections
                )
                if do_break:
                    break
            else:
                order_collections = _SHOW_COLLECTIONS
        return order_collections

    @classmethod
    def get_sort_name_annotations(cls, model, parent_collection, pks, show) -> dict:
        """Annotate sort names for browser subclasses and reader."""
        sort_name_annotations = {}
        if model is Comic:
            order_collections = cls._get_order_collections(parent_collection, pks, show)
            for order_collection in order_collections:
                collection_name = COLLECTION_NAME_MAP[order_collection]
                ann_name = f"{collection_name}_sort_name"
                name_field = "name" if collection_name == "volume" else "sort_name"
                sort_name = F(f"{collection_name}__{name_field}")
                sort_name_annotations[ann_name] = sort_name
        elif model is Volume:
            sort_name_annotations["sort_name"] = F("name")
        return sort_name_annotations

    @staticmethod
    def _volume_name_annotation(model) -> Case:
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
    def annotate_collection_names(cls, qs):
        """Annotate name fields by hoisting them up."""
        # Optimized to only lookup what is used on the frontend
        target = cls.TARGET  #  pyright: ignore[reportAttributeAccessIssue], # ty: ignore[unresolved-attribute]
        if target not in _COLLECTION_NAME_TARGETS:
            return qs
        collection_names = {}
        if qs.model in (Comic, Volume):
            collection_names["series_name"] = F("series__name")
        if qs.model is Comic:
            if target != "reader":
                collection_names["publisher_name"] = F("publisher__name")
                if target == "opds2":
                    collection_names["imprint_name"] = F("imprint__name")
            collection_names.update(
                {
                    "volume_name": F("volume__name"),
                    "volume_number_to": F("volume__number_to"),
                }
            )
        elif qs.model is Imprint:
            collection_names["publisher_name"] = F("publisher__name")
        return qs.annotate(**collection_names)


class UserActiveMixin:
    """View that records user activity."""

    def mark_user_active(self) -> None:
        """Get the app index page."""
        if TYPE_CHECKING:
            self.request: Request  # pyright: ignore[reportUninitializedInstanceVariable]
        if self.request.user and self.request.user.pk:
            task = UserActiveTask(pk=self.request.user.pk)
            LIBRARIAN_QUEUE.put(task)

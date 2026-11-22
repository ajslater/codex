"""
A list's items: issues, and whole collections that stay current.

``PATCH reading-lists/<pk>/items {add: {collection: [pks]}, remove:
{collection: [pks]}}``. Comics are entries added by hand. A publisher,
imprint, series, volume, folder or list is a collection item whose comics
follow it (see :mod:`codex.librarian.scribe.readinglists.live`). Targets
the user may not see are dropped silently, so the answer never reveals
whether one exists. Saved in Codex only: no comic file changes.
"""

from collections.abc import Iterable, Mapping, Sequence
from typing import Any, Final, override

from django.db import transaction
from rest_framework.exceptions import ValidationError
from rest_framework.fields import DictField, IntegerField, ListField
from rest_framework.response import Response
from rest_framework.serializers import Serializer

from codex.librarian.mp_queue import LIBRARIAN_QUEUE
from codex.librarian.scribe.readinglists.live import (
    COLLECTION_KIND,
    ITEM_MODELS,
    ItemRefusedError,
    add_item,
    is_large,
    reconcile_includers,
    reconcile_list,
)
from codex.librarian.scribe.readinglists.tasks import ReadingListLiveSyncTask
from codex.models import Comic
from codex.models.readinglist import ReadingList, ReadingListSource
from codex.views.readinglists.access import ReadingListAccessView, visible_lists
from codex.views.readinglists.entries import add_comics, entry_count, remove_comics

COMICS: Final = "comics"
ITEM_TARGETS: Final = (COMICS, *ITEM_MODELS)


class _TargetsField(DictField):
    """``{collection: [pk, ...]}`` limited to issues and item collections."""

    child = ListField(child=IntegerField(min_value=1), allow_empty=True)

    @override
    def to_internal_value(self, data):
        value = super().to_internal_value(data)
        if unknown := sorted(set(value) - set(ITEM_TARGETS)):
            reason = f"Unknown collection(s): {', '.join(unknown)}."
            raise ValidationError(reason)
        return value


class ReadingListItemsSerializer(Serializer):
    """Input for adding items to and removing items from a list."""

    add = _TargetsField(required=False)
    remove = _TargetsField(required=False)


class ReadingListItemsView(ReadingListAccessView):
    """PATCH: add items to and remove items from one list, in bulk."""

    def _visible(self, collection: str, pks: Sequence[int]) -> list[int]:
        """Keep the targets the user may see, in the order asked."""
        user = self.request.user
        if collection == "arcs":
            queryset = visible_lists(user)
        else:
            model = Comic if collection == COMICS else ITEM_MODELS[collection]
            # Writes land on rows whose file is briefly missing.
            acl = self.get_acl_filter(model, user, include_missing=True)
            queryset = model.objects.filter(acl)
        seen = set(queryset.filter(pk__in=set(pks)).values_list("pk", flat=True))
        return [pk for pk in dict.fromkeys(pks) if pk in seen]

    def _add_items(
        self, reading_list: ReadingList, targets: Mapping[str, Sequence[int]]
    ) -> tuple[list[ReadingListSource], list[dict[str, Any]]]:
        added: list[ReadingListSource] = []
        refused: list[dict[str, Any]] = []
        for collection in ITEM_MODELS:
            for pk in self._visible(collection, targets.get(collection, ())):
                if ReadingListSource.objects.filter(
                    reading_list=reading_list,
                    kind=COLLECTION_KIND,
                    collection=collection,
                    target_id=pk,
                ).exists():
                    continue
                try:
                    added.append(add_item(reading_list, collection, pk))
                except ItemRefusedError as exc:
                    refused.append(
                        {"collection": collection, "pk": pk, "reason": str(exc)}
                    )
        return added, refused

    @staticmethod
    def _remove_items(
        reading_list: ReadingList, targets: Mapping[str, Sequence[int]]
    ) -> int:
        removed = 0
        for collection in ITEM_MODELS:
            if pks := targets.get(collection):
                items = ReadingListSource.objects.filter(
                    reading_list=reading_list,
                    kind=COLLECTION_KIND,
                    collection=collection,
                    target_id__in=pks,
                )
                removed += items.count()
                # Their live entries go with them.
                items.delete()
        return removed

    @staticmethod
    def _sync(reading_list: ReadingList, added: Iterable[ReadingListSource]) -> bool:
        """Sync the list now, or queue it when an item is large; return queued."""
        if any(
            item.target_id is not None and is_large(item.collection, item.target_id)
            for item in added
        ):
            LIBRARIAN_QUEUE.put(
                ReadingListLiveSyncTask(list_pks=(reading_list.pk,), force=True)
            )
            return True
        reconcile_list(reading_list)
        reconcile_includers(reading_list)
        return False

    def patch(self, *_args, **_kwargs) -> Response:
        """Apply ``{add: {collection: [pks]}, remove: {collection: [pks]}}``."""
        reading_list = self.get_reading_list()
        serializer = ReadingListItemsSerializer(data=self.request.data)
        serializer.is_valid(raise_exception=True)
        add = serializer.validated_data.get("add", {})
        remove = serializer.validated_data.get("remove", {})
        # One change: a failed add must not leave the removes applied.
        with transaction.atomic():
            result = remove_comics(reading_list, remove.get(COMICS, ()))
            result["removed"] += self._remove_items(reading_list, remove)
            added, refused = self._add_items(reading_list, add)
            comics = add_comics(
                reading_list, self._visible(COMICS, add.get(COMICS, ()))
            )
        queued = self._sync(reading_list, added)
        result["refused"] += refused
        return Response(
            {
                **result,
                "added": comics + len(added),
                "queued": queued,
                "count": entry_count(reading_list),
            }
        )

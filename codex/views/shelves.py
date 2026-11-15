"""
Shelf views.

A shelf is a signed-in user's named grouping of browsable targets. Every
view here is authenticated-only and scoped to the requesting user: shelves
are persistent intent, not session state, and are never shared.
"""

from django.db import IntegrityError
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from codex.models.settings import SettingsBrowserFilters
from codex.models.shelf import SHELF_COLLECTION_MODELS, Shelf, ShelfItem
from codex.serializers.shelf import ShelfItemsSerializer, ShelfNameSerializer
from codex.views.auth import AuthFilterGenericAPIView


def _empty_items() -> dict[str, list[int]]:
    return {collection: [] for collection in SHELF_COLLECTION_MODELS}


def _shelf_repr(shelf: Shelf, items: dict[str, list[int]] | None = None) -> dict:
    return {
        "pk": shelf.pk,
        "name": shelf.name,
        "items": _empty_items() if items is None else items,
    }


class _ShelfAuthView(AuthFilterGenericAPIView):
    """Authenticated-only base scoped to the requesting user's shelves."""

    permission_classes = (IsAuthenticated,)

    def _get_shelf(self) -> Shelf | None:
        """
        Return the requesting user's shelf for the url pk, or None.

        Another user's shelf is indistinguishable from a missing one.
        """
        return Shelf.objects.filter(
            user=self.request.user, pk=self.kwargs["pk"]
        ).first()

    def _validated_name(self) -> str:
        serializer = ShelfNameSerializer(data=self.request.data)
        serializer.is_valid(raise_exception=True)
        return serializer.validated_data["name"]

    @staticmethod
    def _duplicate_name_response() -> Response:
        return Response(
            {"detail": "You already have a shelf with that name."}, status=400
        )


class ShelfListView(_ShelfAuthView):
    """GET: the user's shelves and their items. POST: create a shelf."""

    def get(self, *_args, **_kwargs) -> Response:
        """Return ``{shelves: [{pk, name, items: {collection: [ids]}}]}``."""
        user = self.request.user
        shelves = Shelf.objects.filter(user=user).order_by("name", "pk")
        items_by_shelf: dict[int, dict[str, list[int]]] = {
            shelf.pk: _empty_items() for shelf in shelves
        }
        rows = (
            ShelfItem.objects.filter(shelf__user=user)
            .order_by("pk")
            .values_list("shelf_id", "collection", "target_id")
        )
        for shelf_id, collection, target_id in rows:
            items = items_by_shelf.get(shelf_id)
            if items is not None and collection in items:
                items[collection].append(target_id)
        return Response(
            {
                "shelves": [
                    _shelf_repr(shelf, items_by_shelf[shelf.pk]) for shelf in shelves
                ]
            }
        )

    def post(self, *_args, **_kwargs) -> Response:
        """Create an empty shelf."""
        name = self._validated_name()
        user = self.request.user
        if Shelf.objects.filter(user=user, name=name).exists():
            return self._duplicate_name_response()
        try:
            shelf = Shelf.objects.create(user=user, name=name)
        except IntegrityError:
            # Lost a race with an identical create.
            return self._duplicate_name_response()
        return Response(_shelf_repr(shelf), status=201)


class ShelfDetailView(_ShelfAuthView):
    """PATCH: rename a shelf. DELETE: delete it and its items."""

    def patch(self, *_args, **_kwargs) -> Response:
        """Rename the shelf."""
        shelf = self._get_shelf()
        if shelf is None:
            return Response(status=404)
        name = self._validated_name()
        if name != shelf.name:
            clash = Shelf.objects.filter(user=self.request.user, name=name).exclude(
                pk=shelf.pk
            )
            if clash.exists():
                return self._duplicate_name_response()
            shelf.name = name
            try:
                shelf.save(update_fields=("name", "updated_at"))
            except IntegrityError:
                return self._duplicate_name_response()
        return Response({"pk": shelf.pk, "name": shelf.name})

    def _forget_shelf_in_settings(self, shelf_pk: int) -> None:
        """
        Drop a deleted shelf from the owner's stored shelves filters.

        Covers the live browser and OPDS settings rows and every saved
        view, so none of them is left filtering on a shelf that no longer
        exists (which would match nothing).
        """
        filters_rows = SettingsBrowserFilters.objects.filter(
            browser__user=self.request.user
        ).exclude(shelves=[])
        for filters in filters_rows:
            kept = [pk for pk in filters.shelves if pk != shelf_pk]
            if kept != filters.shelves:
                filters.shelves = kept
                filters.save(update_fields=("shelves", "updated_at"))

    def delete(self, *_args, **_kwargs) -> Response:
        """Delete the shelf. Idempotent."""
        shelf = self._get_shelf()
        if shelf is not None:
            shelf_pk = shelf.pk
            shelf.delete()
            self._forget_shelf_in_settings(shelf_pk)
        return Response(status=204)


class ShelfItemsView(_ShelfAuthView):
    """PATCH: add targets to and remove targets from one shelf, in bulk."""

    def _visible_target_ids(self, collection: str, target_ids) -> list[int]:
        """
        Keep only the targets the user may see.

        Library and age-rating ACL, the same gate the browser applies.
        Hidden and missing targets are dropped silently, so the response
        never reveals whether a row the user cannot see exists.
        """
        model = SHELF_COLLECTION_MODELS[collection]
        acl_filter = self.get_acl_filter(model, self.request.user)
        return list(
            model.objects.filter(acl_filter, pk__in=set(target_ids))
            .values_list("pk", flat=True)
            .distinct()
        )

    def _add(self, shelf: Shelf, targets: dict[str, list[int]]) -> int:
        new_items = []
        for collection, target_ids in targets.items():
            if not target_ids:
                continue
            visible = self._visible_target_ids(collection, target_ids)
            existing = set(
                ShelfItem.objects.filter(
                    shelf=shelf, collection=collection, target_id__in=visible
                ).values_list("target_id", flat=True)
            )
            new_items += [
                ShelfItem(shelf=shelf, collection=collection, target_id=target_id)
                for target_id in visible
                if target_id not in existing
            ]
        if new_items:
            # One statement, so cachalot invalidates the table once.
            ShelfItem.objects.bulk_create(new_items, ignore_conflicts=True)
        return len(new_items)

    @staticmethod
    def _remove(shelf: Shelf, targets: dict[str, list[int]]) -> int:
        removed = 0
        for collection, target_ids in targets.items():
            if not target_ids:
                continue
            count, _ = ShelfItem.objects.filter(
                shelf=shelf, collection=collection, target_id__in=target_ids
            ).delete()
            removed += count
        return removed

    def patch(self, *_args, **_kwargs) -> Response:
        """Apply ``{add: {collection: [ids]}, remove: {collection: [ids]}}``."""
        shelf = self._get_shelf()
        if shelf is None:
            return Response(status=404)
        serializer = ShelfItemsSerializer(data=self.request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data
        removed = self._remove(shelf, data.get("remove", {}))
        added = self._add(shelf, data.get("add", {}))
        return Response({"added": added, "removed": removed})

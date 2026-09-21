"""Lazy metadata-import view."""

from rest_framework.response import Response

from codex.collection import Collection
from codex.librarian.mp_queue import LIBRARIAN_QUEUE
from codex.librarian.scribe.tasks import LazyImportComicsTask
from codex.serializers.mixins import OKSerializer
from codex.views.auth import AuthFilterGenericAPIView
from codex.views.const import COLLECTION_MODEL_MAP

# Browse collections that resolve to a set of comics for lazy metadata import.
_LAZY_IMPORT_COLLECTIONS = frozenset({Collection.COMIC, Collection.FOLDER})


class LazyImportView(AuthFilterGenericAPIView):
    """Queue a lazy metadata import for the comics under a browse collection."""

    serializer_class = OKSerializer

    def _get_visible_pks(self, collection: str) -> frozenset[int]:
        """
        Narrow the caller's raw URL pks to rows they are allowed to reach.

        The librarian trusts whatever pks arrive on its queue, so the
        library-group and age-rating ACL has to be applied here. The
        filter is applied directly rather than through
        ``get_filtered_queryset``: that seam drags in the caller's saved
        search and filter params, and for ``folders`` it resolves to the
        ancestor-inclusive ``folders`` m2m, which would silently widen
        the target set instead of narrowing it.
        """
        pks = self.kwargs.get("pks") or ()
        model = COLLECTION_MODEL_MAP.get(collection)
        if not pks or not model:
            return frozenset()
        acl_filter = self.get_acl_filter(model, self.request.user)
        return frozenset(
            model.objects.filter(acl_filter, pk__in=pks)
            .distinct()
            .values_list("pk", flat=True)
        )

    def post(self, *args, **kwargs) -> Response:
        """Enqueue a lazy-import task for a comics / folders collection."""
        collection = self.kwargs.get("collection", "")
        if collection in _LAZY_IMPORT_COLLECTIONS and (
            pks := self._get_visible_pks(collection)
        ):
            LIBRARIAN_QUEUE.put(LazyImportComicsTask(collection=collection, pks=pks))
        serializer = self.get_serializer()
        return Response(serializer.data)

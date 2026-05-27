"""
API v4 favorites endpoints.

Plan: ``GET /api/v4/favorites`` returns all favorites by collection;
``PUT/DELETE /api/v4/favorites/{collection}/{id}`` toggle one
favorite. Internally the v3 views own a single-letter ``group``
kwarg; this layer rewrites the collection name into the matching
group letter using :data:`codex.urls.converters.COLLECTION_TO_GROUP`.
"""

from typing import TYPE_CHECKING, override

from codex.urls.converters import COLLECTION_TO_GROUP
from codex.views.favorites import FavoriteDetailView, FavoriteListView
from codex.views.v4.common import EnvelopeJSONRenderer

if TYPE_CHECKING:
    from rest_framework.request import Request


class V4FavoritesListView(FavoriteListView):
    """``GET /api/v4/favorites`` — keyed by single-letter group code (v3 shape)."""

    renderer_classes = (EnvelopeJSONRenderer,)


class V4FavoriteDetailView(FavoriteDetailView):
    """``PUT|DELETE /api/v4/favorites/{collection}/{id}`` — translates collection."""

    renderer_classes = (EnvelopeJSONRenderer,)

    if TYPE_CHECKING:
        kwargs: dict

    @override
    def initial(self, request: "Request", *args, **kwargs):
        """Rewrite collection → single-letter group for the v3 handler."""
        collection = self.kwargs.pop("collection", None)
        if collection is not None:
            self.kwargs["group"] = COLLECTION_TO_GROUP[collection]
        super().initial(request, *args, **kwargs)

"""Favorite views."""

from typing import TYPE_CHECKING, override

from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from codex.models.favorite import FAVORITE_COLLECTION_MODELS, Favorite
from codex.views.auth import AuthFilterGenericAPIView

if TYPE_CHECKING:
    from rest_framework.request import Request


class _FavoriteAuthMixin(AuthFilterGenericAPIView):
    """Authenticated-only base — favorites are persistent intent, not session state."""

    permission_classes = (IsAuthenticated,)


class FavoriteListView(_FavoriteAuthMixin):
    """GET: per-collection ids of the requesting user's favorites."""

    def get(self, *_args, **_kwargs) -> Response:
        """Return ``{collection: [target_id, ...]}`` for the user."""
        # ``Favorite.collection`` is the collection vocabulary, which is exactly
        # the wire shape — no translation needed.
        favorites_by_collection: dict[str, list[int]] = {
            collection: [] for collection in FAVORITE_COLLECTION_MODELS
        }
        rows = Favorite.objects.filter(user=self.request.user).values_list(
            "collection", "target_id"
        )
        for collection, target_id in rows:
            if collection in favorites_by_collection:
                favorites_by_collection[collection].append(target_id)
        return Response(favorites_by_collection)


class FavoriteDetailView(_FavoriteAuthMixin):
    """PUT/DELETE: idempotent toggle of a single (collection, target_id) favorite."""

    @override
    def initial(self, request: "Request", *args, **kwargs):
        """
        Normalize the ``collection`` URL kwarg into engine shape.

        The collection name *is* the favorite collection code now, so the
        value passes through unchanged. We set ``pks`` here too: it both
        records "no parent ids" and trips ``AuthMixin.initial``'s
        ``"pks" not in kwargs`` guard so the inherited
        ``_translate_browser_kwargs`` is skipped — favorites have no
        publishers→root special case and never carry ``parent_ids``.
        """
        collection = self.kwargs.pop("collection", None)
        if collection is not None:
            self.kwargs["collection"] = collection
            self.kwargs["pks"] = ()
        super().initial(request, *args, **kwargs)

    def _resolve_target(self):
        """Return (collection_code, target_id, model) or a Response on error."""
        collection_code = self.kwargs["collection"]
        target_id = self.kwargs["target_id"]
        model = FAVORITE_COLLECTION_MODELS.get(collection_code)
        if model is None:
            return Response(
                {"detail": f"Unknown favorite collection {collection_code!r}."},
                status=400,
            )
        return collection_code, target_id, model

    def put(self, *_args, **_kwargs) -> Response:
        """Idempotently mark a target as favorited."""
        resolved = self._resolve_target()
        if isinstance(resolved, Response):
            return resolved
        collection_code, target_id, model = resolved

        # ACL: target must be visible under the user's library + age-rating ACL.
        # 404 (not 403) so we don't reveal whether the row exists.
        acl_filter = self.get_acl_filter(model, self.request.user)
        if not model.objects.filter(acl_filter, pk=target_id).exists():
            return Response(status=404)

        _, created = Favorite.objects.get_or_create(
            user=self.request.user,
            collection=collection_code,
            target_id=target_id,
        )
        return Response(status=201 if created else 200)

    def delete(self, *_args, **_kwargs) -> Response:
        """Idempotently un-favorite a target."""
        resolved = self._resolve_target()
        if isinstance(resolved, Response):
            return resolved
        collection_code, target_id, _model = resolved

        Favorite.objects.filter(
            user=self.request.user,
            collection=collection_code,
            target_id=target_id,
        ).delete()
        return Response(status=204)

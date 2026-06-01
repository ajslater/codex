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
    """GET: per-group ids of the requesting user's favorites."""

    def get(self, *_args, **_kwargs) -> Response:
        """Return ``{collection: [target_id, ...]}`` for the user."""
        # ``Favorite.group`` is the collection vocabulary, which is exactly
        # the wire shape — no translation needed.
        favorites_by_group: dict[str, list[int]] = {
            group: [] for group in FAVORITE_COLLECTION_MODELS
        }
        rows = Favorite.objects.filter(user=self.request.user).values_list(
            "group", "target_id"
        )
        for group, target_id in rows:
            if group in favorites_by_group:
                favorites_by_group[group].append(target_id)
        return Response(favorites_by_group)


class FavoriteDetailView(_FavoriteAuthMixin):
    """PUT/DELETE: idempotent toggle of a single (group, target_id) favorite."""

    @override
    def initial(self, request: "Request", *args, **kwargs):
        """
        Rename the ``collection`` URL kwarg to ``group``.

        The collection name *is* the favorite group code now, so this is
        a straight rename. Bypasses ``AuthMixin._translate_browser_kwargs``:
        favorites have no publishers→root special case and never carry
        ``parent_ids``.
        """
        collection = self.kwargs.pop("collection", None)
        if collection is not None:
            self.kwargs["group"] = collection
        super().initial(request, *args, **kwargs)

    def _resolve_target(self):
        """Return (group_code, target_id, model) or a Response on error."""
        group_code = self.kwargs["group"]
        target_id = self.kwargs["target_id"]
        model = FAVORITE_COLLECTION_MODELS.get(group_code)
        if model is None:
            return Response(
                {"detail": f"Unknown favorite group {group_code!r}."},
                status=400,
            )
        return group_code, target_id, model

    def put(self, *_args, **_kwargs) -> Response:
        """Idempotently mark a target as favorited."""
        resolved = self._resolve_target()
        if isinstance(resolved, Response):
            return resolved
        group_code, target_id, model = resolved

        # ACL: target must be visible under the user's library + age-rating ACL.
        # 404 (not 403) so we don't reveal whether the row exists.
        acl_filter = self.get_acl_filter(model, self.request.user)
        if not model.objects.filter(acl_filter, pk=target_id).exists():
            return Response(status=404)

        _, created = Favorite.objects.get_or_create(
            user=self.request.user,
            group=group_code,
            target_id=target_id,
        )
        return Response(status=201 if created else 200)

    def delete(self, *_args, **_kwargs) -> Response:
        """Idempotently un-favorite a target."""
        resolved = self._resolve_target()
        if isinstance(resolved, Response):
            return resolved
        group_code, target_id, _model = resolved

        Favorite.objects.filter(
            user=self.request.user,
            group=group_code,
            target_id=target_id,
        ).delete()
        return Response(status=204)

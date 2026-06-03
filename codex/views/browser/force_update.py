"""Force update browser view: re-import metadata for a filtered comic set."""

from collections.abc import Sequence
from types import MappingProxyType
from typing import override

from drf_spectacular.utils import extend_schema
from rest_framework.permissions import BasePermission, IsAdminUser
from rest_framework.response import Response

from codex.librarian.mp_queue import LIBRARIAN_QUEUE
from codex.librarian.scribe.tasks import ForceUpdateComicsTask
from codex.models.comic import Comic
from codex.serializers.mixins import OKSerializer
from codex.views.browser.filters.filter import BrowserFilterView


class ForceUpdateView(BrowserFilterView):
    """Force a metadata re-import for every comic under a collection + filters."""

    permission_classes: Sequence[type[BasePermission]] = (IsAdminUser,)
    serializer_class = OKSerializer
    TARGET: str = "force_update"

    def __init__(self, *args, **kwargs) -> None:
        """Init acl properties."""
        super().__init__(*args, **kwargs)
        self.init_group_acl()

    @property
    @override
    def params(self):
        """Retrieve params from the request without saving them to settings."""
        if self._params is None:
            params = self.load_params_from_settings()
            self._params = MappingProxyType(params)
        return self._params

    @extend_schema(request=None, responses=serializer_class)
    def post(self, *_args, **_kwargs) -> Response:
        """Enqueue a force-update task for every comic matching the filters."""
        collection = self.kwargs.get("collection")
        pks = self.kwargs.get("pks")
        comic_pks = frozenset(
            self.get_filtered_queryset(
                Comic, collection=collection, pks=pks
            ).values_list("pk", flat=True)
        )
        if comic_pks:
            task = ForceUpdateComicsTask(comic_pks=comic_pks)
            LIBRARIAN_QUEUE.put(task)
        return Response()

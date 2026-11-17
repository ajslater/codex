"""Add a browser selection to a reading list: any collection, as its comics."""

from functools import cached_property
from types import MappingProxyType
from typing import override

from django.db.models import Q
from rest_framework.exceptions import NotFound, PermissionDenied, ValidationError
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from codex.collection import Collection
from codex.models import Comic
from codex.models.readinglist import ReadingList
from codex.views.browser.filters.filter import BrowserFilterView
from codex.views.readinglists.access import can_edit
from codex.views.readinglists.entries import add_comics

# The order comics of a selection join a list in.
_READING_ORDER = (
    "series__sort_name",
    "volume__name",
    "issue_number",
    "issue_suffix",
    "date",
    "pk",
)
_COLLECTIONS = frozenset(collection.value for collection in Collection) - {"root"}


class ReadingListAddView(BrowserFilterView):
    """
    POST ``{targets: {collection: [pks]}}``: add their comics to the list.

    A series, a folder or another list adds every comic in it the user may
    see, in reading order, after the list's last entry. Saved in Codex
    only: no comic file changes.
    """

    permission_classes = (IsAuthenticated,)
    # Folders reach every comic beneath them, as a force update does.
    TARGET: str = "force_update"

    def __init__(self, *args, **kwargs) -> None:
        """Init group ACL state."""
        super().__init__(*args, **kwargs)
        self.init_group_acl()

    @cached_property
    @override
    def params(self):
        """Load the browser settings; the selection ignores their filters."""
        return MappingProxyType(self.load_params_from_settings())

    def _reading_list(self) -> ReadingList:
        reading_list = ReadingList.objects.filter(
            self.reading_list_visibility_filter(self.request.user),
            pk=self.kwargs["pk"],
        ).first()
        if reading_list is None:
            reason = "No such reading list."
            raise NotFound(reason)
        if not can_edit(self.request.user, reading_list):
            reason = "You may not change this reading list."
            raise PermissionDenied(reason)
        return reading_list

    def _comic_pks(self, targets: dict) -> list[int]:
        query = Q(pk__in=())
        for collection, pks in targets.items():
            if collection not in _COLLECTIONS:
                reason = f"Unknown collection {collection!r}."
                raise ValidationError(reason)
            int_pks = tuple(int(pk) for pk in pks or () if str(pk).isdigit())
            if int_pks:
                query |= self.get_collection_filter(collection, int_pks)
        acl = self.get_acl_filter(Comic, self.request.user)
        rows = (
            Comic.objects.filter(acl & query)
            .order_by(*_READING_ORDER)
            .values_list("pk", flat=True)
        )
        return list(dict.fromkeys(rows))

    def post(self, *_args, **_kwargs) -> Response:
        """Add the selection's comics, in reading order, at the end."""
        reading_list = self._reading_list()
        targets = self.request.data.get("targets") or {}
        if not isinstance(targets, dict):
            reason = "targets must map collections to pks."
            raise ValidationError(reason)
        added = add_comics(reading_list, self._comic_pks(targets))
        return Response({"added": added, "name": reading_list.name})

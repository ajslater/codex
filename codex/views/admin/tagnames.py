"""
Admin tag name suggestions.

The tag editor's comboboxes ask for existing names as the user types so a
correction can pick the library's spelling instead of retyping it. The
importer matches names exactly, so a typo would quietly create a new row.

Each request returns at most ``LIMIT`` names, prefix matches first, plus
whether that is every match. A small vocabulary comes back complete on the
first request and the client never asks again; a large one stays filtered
here, per keystroke.
"""

from functools import cached_property
from types import MappingProxyType
from typing import Final

from django.db.models import Case, CharField, QuerySet, Value, When
from django.db.models.functions import Lower
from drf_spectacular.utils import extend_schema
from rest_framework.exceptions import NotFound
from rest_framework.response import Response

from codex.models.base import BaseModel
from codex.models.collections import Imprint, Publisher, Series, Volume
from codex.models.named import (
    Character,
    CreditPerson,
    Genre,
    Location,
    SeriesGroup,
    Story,
    StoryArc,
    Tag,
    Team,
    Universe,
)
from codex.serializers.admin.tagging import (
    AdminTagNamesInputSerializer,
    AdminTagNamesSerializer,
)
from codex.views.admin.auth import AdminGenericAPIView
from codex.views.settings import CREDIT_PERSON_UI_FIELD, STORY_ARC_UI_FIELD

#: Most names one request returns.
LIMIT: Final = 100

#: Every field that may be asked for, by the editor's field key. Credits and
#: story arcs reach their names through a through-model on Comic, so they
#: name the named model directly.
_FIELD_MODELS: Final[MappingProxyType[str, type[BaseModel]]] = MappingProxyType(
    {
        "publisher": Publisher,
        "imprint": Imprint,
        "series": Series,
        "volume": Volume,
        "genres": Genre,
        "characters": Character,
        "teams": Team,
        "locations": Location,
        "series_groups": SeriesGroup,
        "stories": Story,
        "tags": Tag,
        "universes": Universe,
        CREDIT_PERSON_UI_FIELD: CreditPerson,
        STORY_ARC_UI_FIELD: StoryArc,
    }
)
#: Parent names that narrow a field's suggestions, outermost first.
_SCOPES: Final = MappingProxyType(
    {
        "imprint": ("publisher",),
        "series": ("publisher", "imprint"),
        "volume": ("publisher", "imprint", "series"),
    }
)


class AdminTagNamesView(AdminGenericAPIView):
    """Existing names for one tag field, filtered by what the user typed."""

    serializer_class = AdminTagNamesSerializer
    input_serializer_class = AdminTagNamesInputSerializer

    @cached_property
    def params(self) -> MappingProxyType[str, str]:
        """Validate the query params."""
        serializer = self.input_serializer_class(data=self.request.GET)
        serializer.is_valid(raise_exception=True)
        return MappingProxyType(dict(serializer.validated_data))

    @staticmethod
    def _model_for(field: str) -> type[BaseModel]:
        """Look up the named model, refusing anything off the allowlist."""
        try:
            return _FIELD_MODELS[field]
        except KeyError as exc:
            reason = f"No name suggestions for {field}."
            raise NotFound(reason) from exc

    @staticmethod
    def _is_text(model: type[BaseModel]) -> bool:
        """Whether names are text. Volume.name is an integer column."""
        return isinstance(model._meta.get_field("name"), CharField)

    @classmethod
    def _base_qs(cls, model: type[BaseModel]) -> QuerySet:
        """Every row with a name; the default imprint's blank name is none."""
        qs = model.objects.exclude(name__isnull=True)
        # An integer column can't be compared to "".
        return qs.exclude(name="") if cls._is_text(model) else qs

    def _scoped(self, field: str, qs: QuerySet) -> QuerySet:
        """Narrow to the form's parents, ignoring the ones left blank."""
        scope_filter = {
            f"{parent}__name": value
            for parent in _SCOPES.get(field, ())
            if (value := self.params.get(parent))
        }
        return qs.filter(**scope_filter) if scope_filter else qs

    @staticmethod
    def _searched(qs: QuerySet, q: str, *, text: bool) -> QuerySet:
        """Filter by ``q``, prefix matches first so the cap never drops them."""
        # Text sorts ignoring case; integers sort as numbers, not as text.
        order = Lower("name") if text else "name"
        if not q:
            return qs.order_by(order)
        return (
            qs.filter(name__icontains=q)
            .annotate(
                prefix=Case(When(name__istartswith=q, then=Value(0)), default=Value(1))
            )
            .order_by("prefix", order)
        )

    @extend_schema(parameters=[input_serializer_class])
    def get(self, *_args, **kwargs) -> Response:
        """Get at most ``LIMIT`` existing names for the field."""
        field = kwargs["field"]
        model = self._model_for(field)
        qs = self._scoped(field, self._base_qs(model))
        qs = self._searched(qs, self.params.get("q", ""), text=self._is_text(model))
        # Names repeat across parents (Series under two imprints), so
        # distinct. One more than the cap tells complete from truncated
        # without a COUNT.
        names = list(qs.values_list("name", flat=True).distinct()[: LIMIT + 1])
        data = {
            "field": field,
            "names": names[:LIMIT],
            "complete": len(names) <= LIMIT,
        }
        serializer = self.get_serializer(data)
        return Response(serializer.data)

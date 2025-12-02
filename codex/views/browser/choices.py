"""View for marking comics read and unread."""

from itertools import chain
from types import MappingProxyType
from typing import Any

from caseconverter import snakecase
from django.db.models import QuerySet
from drf_spectacular.utils import extend_schema
from rest_framework.response import Response
from rest_framework.serializers import BaseSerializer
from typing_extensions import override

from codex.choices.browser import DUMMY_NULL_NAME, VUETIFY_NULL_CODE
from codex.models import (
    Comic,
    CreditPerson,
    StoryArc,
)
from codex.models.identifier import IdentifierSource
from codex.models.named import Universe
from codex.serializers.browser.choices import (
    BrowserChoicesFilterSerializer,
    BrowserFilterChoicesSerializer,
)
from codex.serializers.browser.settings import BrowserFilterChoicesInputSerializer
from codex.views.browser.filters.filter import BrowserFilterView
from codex.views.session import (
    CREDIT_PERSON_UI_FIELD,
    IDENTIFIER_TYPE_UI_FIELD,
    STORY_ARC_UI_FIELD,
)

_FIELD_TO_REL_MODEL_MAP = MappingProxyType(
    {
        CREDIT_PERSON_UI_FIELD: (
            "credits__person",
            CreditPerson,
        ),
        IDENTIFIER_TYPE_UI_FIELD: (
            "identifiers__source",
            IdentifierSource,
        ),
        STORY_ARC_UI_FIELD: (
            "story_arc_numbers__story_arc",
            StoryArc,
        ),
    }
)
_BACK_REL_MAP = MappingProxyType(
    {
        CreditPerson: "credit__",
        StoryArc: "storyarcnumber__",
        IdentifierSource: "identifier__",
    }
)
_NULL_NAMED_ROW = MappingProxyType({"pk": VUETIFY_NULL_CODE, "name": DUMMY_NULL_NAME})
_NULL_NAMED_ROW_ITERABLE = (_NULL_NAMED_ROW,)


class BrowserChoicesViewBase(BrowserFilterView):
    """Get choices for filter dialog."""

    input_serializer_class: type[BrowserFilterChoicesInputSerializer] = (  # pyright: ignore[reportIncompatibleVariableOverride]
        BrowserFilterChoicesInputSerializer
    )
    TARGET: str = "choices"

    @staticmethod
    def get_field_choices_query(comic_qs, field_name):
        """Get distinct values for the field."""
        return comic_qs.exclude(**{f"{field_name}__isnull": True}).distinct()

    def get_m2m_field_query(self, model, comic_qs: QuerySet):
        """Get distinct m2m value objects for the relation."""
        back_rel = _BACK_REL_MAP.get(model, "")
        m2m_filter = {f"{back_rel}comic__in": comic_qs}
        return model.objects.filter(**m2m_filter).distinct()

    @staticmethod
    def does_m2m_null_exist(comic_qs, rel):
        """Get if comics exist in the filter without values exists for an m2m field."""
        # Detect if there are null choices. Regretably with another query.
        return comic_qs.filter(**{f"{rel}__isnull": True}).exists()

    def get_rel_and_model(self, field_name):
        """Return the relation and model for the field name."""
        rel_and_model = _FIELD_TO_REL_MODEL_MAP.get(field_name)
        if rel_and_model:
            rel, model = rel_and_model
        else:
            remote_field = getattr(
                Comic._meta.get_field(field_name), "remote_field", None
            )
            rel = field_name
            model = remote_field.model if remote_field else None

        return rel, model

    @override
    def get_object(self) -> QuerySet:
        """Get the comic subquery use for the choices."""
        return self.get_filtered_queryset(Comic)

    @extend_schema(parameters=[input_serializer_class])
    def get(self, *_args, **_kwargs):
        """Return choices."""
        obj = self.get_object()
        serializer = self.get_serializer(obj)
        return Response(serializer.data)


class BrowserChoicesAvailableView(BrowserChoicesViewBase):
    """Get choices for filter dialog."""

    serializer_class: type[BaseSerializer] | None = BrowserFilterChoicesSerializer

    @classmethod
    def _is_field_choices_exists(cls, comic_qs, field_name):
        """Create a pk:name object for fields without tables."""
        qs = cls.get_field_choices_query(comic_qs, field_name)
        return qs.exists()

    def _is_m2m_field_choices_exists(self, model, comic_qs, rel):
        """Get choices with nulls where there are nulls."""
        qs = self.get_m2m_field_query(model, comic_qs)
        qs = qs[:2]
        count = qs.count()
        if count > 1:
            # There are choices
            return True
        if count == 1:
            # There are only choices if a null exists
            return self.does_m2m_null_exist(comic_qs, rel)
        # There is only one or no choices.
        return False

    def _is_filter_field_choices_exists(self, qs: QuerySet, field_name: str):
        rel, m2m_model = self.get_rel_and_model(field_name)

        if m2m_model:
            exists = self._is_m2m_field_choices_exists(m2m_model, qs, rel)
        else:
            exists = self._is_field_choices_exists(qs, field_name)
        try:
            flag = exists
        except TypeError:
            flag = False
        return flag

    @override
    def get_object(self) -> dict[str, Any]:  # pyright: ignore[reportIncompatibleMethodOverride], # ty: ignore[invalid-method-override]
        """Get choice counts."""
        qs = super().get_object()
        filters = self.params.get("filters", {})
        data = {}
        serializer: BrowserFilterChoicesSerializer = self.serializer_class()  # pyright: ignore[reportOptionalCall, reportAssignmentType], # ty: ignore[call-non-callable, invalid-assignment]
        for field_name in serializer.get_fields():
            if field_name == "story_arcs" and qs.model is StoryArc:
                # don't allow filtering on story arc in story arc view.
                continue
            if bool(filters.get(field_name)):
                flag = True
            else:
                flag = self._is_filter_field_choices_exists(qs, field_name)
            data[field_name] = flag
        return data


class BrowserChoicesView(BrowserChoicesViewBase):
    """Get choices for filter dialog."""

    serializer_class: type[BaseSerializer] | None = BrowserChoicesFilterSerializer

    def _get_m2m_field_choices(self, model, comic_qs, rel):
        """Get choices with nulls where there are nulls."""
        iterables = []

        # Choices
        qs = self.get_m2m_field_query(model, comic_qs)
        values = ["pk", "name"]
        if qs.model == Universe:
            values.append("designation")
        qs = qs.values(*values)

        # Add null if it exists
        if self.does_m2m_null_exist(comic_qs, rel):
            iterables.append(_NULL_NAMED_ROW_ITERABLE)

        iterables.append(qs)

        return chain.from_iterable(iterables)

    def _get_field_name(self):
        field_name = self.kwargs.get("field_name", "")
        return snakecase(field_name)

    @override
    def get_object(self) -> dict[str, Any]:  # pyright: ignore[reportIncompatibleMethodOverride], # ty: ignore[invalid-method-override]
        """Return choices with more than one choice."""
        qs = super().get_object()
        field_name = self._get_field_name()
        rel, m2m_model = self.get_rel_and_model(field_name)

        if m2m_model:
            choices = self._get_m2m_field_choices(m2m_model, qs, rel)
        else:
            choices = self.get_field_choices_query(qs, field_name)
            choices = choices.values_list(field_name, flat=True)

        if field_name in ("critical_rating", "file_type"):
            choices = tuple({"pk": choice, "name": choice} for choice in choices)

        return {
            "field_name": field_name,
            "choices": choices,
        }

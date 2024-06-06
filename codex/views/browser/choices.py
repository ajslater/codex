"""View for marking comics read and unread."""

from types import MappingProxyType

import pycountry
from caseconverter import snakecase
from django.db.models import QuerySet
from drf_spectacular.utils import extend_schema
from rest_framework.response import Response

from codex.logger.logging import get_logger
from codex.models import (
    Comic,
    ContributorPerson,
    StoryArc,
)
from codex.models.named import IdentifierType
from codex.serializers.browser.choices import CHOICES_SERIALIZER_CLASS_MAP
from codex.serializers.browser.filters import (
    BrowserFilterChoicesSerializer,
    CharListField,
)
from codex.serializers.models.pycountry import PyCountrySerializer
from codex.views.browser.filters.annotations import (
    BrowserAnnotationsFilterView,
)

LOG = get_logger(__name__)

_FIELD_TO_REL_MODEL_MAP = MappingProxyType(
    {
        BrowserAnnotationsFilterView.CONTRIBUTOR_PERSON_UI_FIELD: (
            "contributors__person",
            ContributorPerson,
        ),
        BrowserAnnotationsFilterView.STORY_ARC_UI_FIELD: (
            "story_arc_numbers__story_arc",
            StoryArc,
        ),
        BrowserAnnotationsFilterView.IDENTIFIER_TYPE_UI_FIELD: (
            "identifiers__identifier_type",
            IdentifierType,
        ),
    }
)
_BACK_REL_MAP = MappingProxyType(
    {
        ContributorPerson: "contributor__",
        StoryArc: "storyarcnumber__",
        IdentifierType: "identifier__",
    }
)
_NULL_NAMED_ROW = MappingProxyType({"pk": -1, "name": "_none_"})


class BrowserChoicesViewBase(BrowserAnnotationsFilterView):
    """Get choices for filter dialog."""

    SERIALIZER_MANY = False
    TARGET = "choices"

    @staticmethod
    def get_field_choices_query(comic_qs, field_name):
        """Get distinct values for the field."""
        return (
            comic_qs.exclude(**{field_name: None})
            .values_list(field_name, flat=True)
            .distinct()
        )

    def get_m2m_field_query(self, model, comic_qs: QuerySet):
        """Get distinct m2m value objects for the relation."""
        back_rel = _BACK_REL_MAP.get(model, "")
        m2m_filter = {f"{back_rel}comic__in": comic_qs}
        return model.objects.filter(**m2m_filter).values("pk", "name").distinct()

    @staticmethod
    def does_m2m_null_exist(comic_qs, rel):
        """Get if comics exist in the filter without values exists for an m2m field."""
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

    def get_object(self):
        """Get the comic subquery use for the choices."""
        return self.get_filtered_queryset(Comic)

    @extend_schema(request=BrowserAnnotationsFilterView.input_serializer_class)
    def get(self, *_args, **_kwargs):
        """Return choices."""
        self.init_request()
        obj = self.get_object()
        serializer = self.get_serializer(obj, many=self.SERIALIZER_MANY)
        return Response(serializer.data)


class BrowserChoicesAvailableView(BrowserChoicesViewBase):
    """Get choices for filter dialog."""

    serializer_class = BrowserFilterChoicesSerializer

    @classmethod
    def _get_field_choices_count(cls, comic_qs, field_name):
        """Create a pk:name object for fields without tables."""
        qs = cls.get_field_choices_query(comic_qs, field_name)
        return qs.count()

    def _get_m2m_field_choices_count(self, model, comic_qs, rel):
        """Get choices with nulls where there are nulls."""
        m2m_qs = self.get_m2m_field_query(model, comic_qs)
        m2m_qs = m2m_qs.values("pk")
        count = m2m_qs.count()

        # Detect if there are null choices.
        # Regretabbly with another query, but doing a forward query
        # on the comic above restricts all results to only the filtered
        # rows. :(
        if self.does_m2m_null_exist(comic_qs, rel):
            count += 1

        return count

    def get_object(self):
        """Get choice counts."""
        qs = super().get_object()
        filters = self.params.get("filters", {})
        data = {}
        for field_name in self.serializer_class().get_fields():  # type: ignore
            if field_name == "story_arcs" and self.model == StoryArc:
                # don't allow filtering on story arc in story arc view.
                continue
            rel, m2m_model = self.get_rel_and_model(field_name)

            if m2m_model:
                count = self._get_m2m_field_choices_count(m2m_model, qs, rel)
            else:
                count = self._get_field_choices_count(qs, rel)

            try:
                is_filter_set = bool(filters.get(field_name))
                flag = is_filter_set or count > 1  # type: ignore
            except TypeError:
                flag = False
            data[field_name] = flag
        return data


class BrowserChoicesView(BrowserChoicesViewBase):
    """Get choices for filter dialog."""

    # serializer_class = Dynamic class determined in get()
    SERIALIZER_MANY = True
    # HACK get_serializer(data, many=True) requires this to be set for the debug API view
    queryset = Comic.objects.none()

    def _get_field_choices(self, comic_qs, field_name):
        """Create a pk:name object for fields without tables."""
        qs = self.get_field_choices_query(comic_qs, field_name)

        if field_name == "country":
            lookup = pycountry.countries
        elif field_name == "language":
            lookup = pycountry.languages
        else:
            lookup = None

        choices = []
        for val in qs:
            name = PyCountrySerializer.lookup_name(lookup, val) if lookup else val
            choices.append({"pk": val, "name": name})

        return choices

    def _get_m2m_field_choices(self, model, comic_qs, rel):
        """Get choices with nulls where there are nulls."""
        qs = self.get_m2m_field_query(model, comic_qs)

        # Detect if there are null choices.
        # Regretabbly with another query, but doing a forward query
        # on the comic above restrcts all results to only the filtered
        # rows. :(
        if self.does_m2m_null_exist(comic_qs, rel):
            choices = list(qs)
            choices.append(_NULL_NAMED_ROW)
        else:
            choices = qs
        return choices

    def _get_field_name(self):
        field_name = self.kwargs.get("field_name", "")
        return snakecase(field_name)

    def get_serializer_class(self):  # type: ignore
        """Dynamic serializer class."""
        field_name = self._get_field_name()
        return CHOICES_SERIALIZER_CLASS_MAP.get(field_name, CharListField)

    def get_object(self):
        """Return choices with more than one choice."""
        qs = super().get_object()
        field_name = self._get_field_name()
        rel, m2m_model = self.get_rel_and_model(field_name)

        if m2m_model:
            choices = self._get_m2m_field_choices(m2m_model, qs, rel)
        else:
            choices = self._get_field_choices(qs, rel)
        return choices

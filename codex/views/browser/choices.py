"""View for marking comics read and unread."""
import pycountry

from djangorestframework_camel_case.settings import api_settings
from djangorestframework_camel_case.util import camel_to_underscore
from drf_spectacular.utils import extend_schema
from rest_framework.response import Response

from codex.models import Comic, CreditPerson
from codex.serializers.browser import (
    BrowserChoicesSerializer,
    BrowserFilterChoicesSerializer,
)
from codex.serializers.models import PyCountrySerializer
from codex.settings.logging import get_logger
from codex.views.auth import IsAuthenticatedOrEnabledNonUsers
from codex.views.browser.base import BrowserBaseView


LOG = get_logger(__name__)


class BrowserChoicesViewBase(BrowserBaseView):
    """Get choices for filter dialog."""

    permission_classes = [IsAuthenticatedOrEnabledNonUsers]

    CREDITS_PERSON_REL = "credits__person"
    NULL_NAMED_ROW = {"pk": -1, "name": "_none_"}

    @staticmethod
    def get_field_choices_query(field_name, comic_qs):
        """Get distinct values for the field."""
        return comic_qs.values_list(field_name, flat=True).distinct()

    @classmethod
    def get_m2m_field_query(cls, rel, comic_qs, model):
        """Get distinct m2m value objects for the relation."""
        if rel == cls.CREDITS_PERSON_REL:
            comic_rel = "credit__comic"
        else:
            comic_rel = "comic"
        return (
            model.objects.filter(**{f"{comic_rel}__in": comic_qs})
            .prefetch_related(comic_rel)
            .values("pk", "name")
            .distinct()
        )

    @staticmethod
    def does_m2m_null_exist(comic_qs, rel):
        """Get if null values exists for an m2m field."""
        return comic_qs.filter(**{f"{rel}__isnull": True}).exists()

    @classmethod
    def _get_rel_and_model(cls, field_name):
        """Return the relation and model for the field name."""
        if field_name == cls.CREDIT_PERSON_UI_FIELD:
            rel = cls.CREDITS_PERSON_REL
            model = CreditPerson
        else:
            remote_field = getattr(
                Comic._meta.get_field(field_name), "remote_field", None
            )
            rel = field_name
            if remote_field:
                model = remote_field.model
            else:
                model = None

        return rel, model

    def get_object(self):
        """Get the comic subquery use for the choices."""
        object_filter, _ = self.get_query_filters(True, True)
        return Comic.objects.filter(object_filter)


class BrowserChoicesAvailableView(BrowserChoicesViewBase):
    """Get choices for filter dialog."""

    serializer_class = BrowserFilterChoicesSerializer

    CREDITS_PERSON_REL = "credits__person"

    @classmethod
    def _get_field_choices_count(cls, field_name, comic_qs):
        """Create a pk:name object for fields without tables."""
        return cls.get_field_choices_query(field_name, comic_qs).count()

    @classmethod
    def _get_m2m_field_choices_count(cls, rel, comic_qs, model):
        """Get choices with nulls where there are nulls."""
        count = cls.get_m2m_field_query(rel, comic_qs, model).count()

        # Detect if there are null choices.
        # Regretabbly with another query, but doing a forward query
        # on the comic above restricts all results to only the filtered
        # rows. :(
        if cls.does_m2m_null_exist(comic_qs, rel):
            count += 1

        return count

    @extend_schema(request=BrowserBaseView.input_serializer_class)
    def get(self, request, *args, **kwargs):
        """Return all choices with more than one choice."""
        self.parse_params()
        comic_qs = self.get_object()

        data = {}
        for field_name in self.serializer_class().get_fields():  # type: ignore

            rel, m2m_model = self._get_rel_and_model(field_name)

            if m2m_model:
                count = self._get_m2m_field_choices_count(rel, comic_qs, m2m_model)
            else:
                count = self._get_field_choices_count(rel, comic_qs)

            filters = self.params.get("filters", {})
            data[field_name] = count > 1 or field_name in filters

        serializer = self.get_serializer(data)
        return Response(serializer.data)


class BrowserChoicesView(BrowserChoicesViewBase):
    """Get choices for filter dialog."""

    serializer_class = BrowserChoicesSerializer

    @classmethod
    def _get_field_choices(cls, field_name, comic_qs):
        """Create a pk:name object for fields without tables."""
        qs = cls.get_field_choices_query(field_name, comic_qs)

        if field_name == "country":
            lookup = pycountry.countries
        elif field_name == "language":
            lookup = pycountry.languages
        else:
            lookup = None

        choices = []
        for val in qs:
            if lookup:
                name = PyCountrySerializer.lookup_name(lookup, val)
            else:
                name = val
            choices.append({"pk": val, "name": name})

        return choices

    @classmethod
    def _get_m2m_field_choices(cls, rel, comic_qs, model):
        """Get choices with nulls where there are nulls."""
        qs = cls.get_m2m_field_query(rel, comic_qs, model)

        # Detect if there are null choices.
        # Regretabbly with another query, but doing a forward query
        # on the comic above restricts all results to only the filtered
        # rows. :(
        if cls.does_m2m_null_exist(comic_qs, rel):
            choices = list(qs)
            choices.append(cls.NULL_NAMED_ROW)
        else:
            choices = qs
        return choices

    @extend_schema(request=BrowserBaseView.input_serializer_class)
    def get(self, request, *args, **kwargs):
        """Return all choices with more than one choice."""
        self.parse_params()

        field_name = self.kwargs.get("field_name")
        field_name = camel_to_underscore(field_name, **api_settings.JSON_UNDERSCOREIZE)

        rel, m2m_model = self._get_rel_and_model(field_name)

        comic_qs = self.get_object()
        if m2m_model:
            choices = self._get_m2m_field_choices(rel, comic_qs, m2m_model)
        else:
            choices = self._get_field_choices(rel, comic_qs)

        serializer = self.get_serializer(choices, many=True)
        return Response(serializer.data)

"""View for marking comics read and unread."""
import pycountry

from drf_spectacular.utils import extend_schema
from rest_framework.response import Response

from codex.models import Comic, CreditPerson
from codex.serializers.browser import BrowserFilterChoicesSerializer
from codex.serializers.models import PyCountrySerializer
from codex.settings.logging import get_logger
from codex.views.auth import IsAuthenticatedOrEnabledNonUsers
from codex.views.browser.base import BrowserBaseView


LOG = get_logger(__name__)


class BrowserChoicesView(BrowserBaseView):
    """Get choices for filter dialog."""

    permission_classes = [IsAuthenticatedOrEnabledNonUsers]
    serializer_class = BrowserFilterChoicesSerializer

    CREDITS_PERSON_REL = "credits__person"
    NULL_NAMED_ROW = {"pk": None, "name": ""}

    @staticmethod
    def _get_field_choices(field_name, comic_qs):
        """Create a pk:name object for fields without tables."""
        qs = comic_qs.values_list(field_name, flat=True).distinct()

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
        if rel == cls.CREDITS_PERSON_REL:
            comic_rel = "credit__comic"
        else:
            comic_rel = "comic"
        qs = (
            model.objects.filter(**{f"{comic_rel}__in": comic_qs})
            .prefetch_related(comic_rel)
            .values("pk", "name")
            .distinct()
        )

        # Detect if there are null choices.
        # Regretabbly with another query, but doing a forward query
        # on the comic above restricts all results to only the filtered
        # rows. :(
        if comic_qs.filter(**{f"{rel}__isnull": True}).exists():
            choices = list(qs)
            choices.append(cls.NULL_NAMED_ROW)
        else:
            choices = qs
        return choices

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

    @extend_schema(request=BrowserBaseView.input_serializer_class)
    def get(self, request, *args, **kwargs):
        """Return all choices with more than one choice."""
        self.parse_params()
        comic_qs = self.get_object()

        data = {}
        for field_name in self.serializer_class().get_fields():  # type: ignore

            rel, m2m_model = self._get_rel_and_model(field_name)

            if m2m_model:
                choices = self._get_m2m_field_choices(rel, comic_qs, m2m_model)
            else:
                choices = self._get_field_choices(rel, comic_qs)

            filters = self.params.get("filters", {})
            if len(choices) > 1 or field_name in filters:
                # only offer choices when there's more than one choice
                # OR there is a chance to deleselect a selected filter
                data[field_name] = choices

        serializer = self.get_serializer(data)
        return Response(serializer.data)

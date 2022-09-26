"""View for marking comics read and unread."""
import pycountry

from drf_spectacular.utils import extend_schema
from rest_framework.response import Response

from codex.models import Comic
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

    @staticmethod
    def _get_m2m_field_choices(rel, comic_qs):
        """Get choices with nulls where there are nulls."""
        qs = (
            comic_qs.prefetch_related(rel)
            .values_list(f"{rel}__pk", f"{rel}__name")
            .distinct()
        )
        choices = []
        for pk, name in qs:
            if name is None:
                name = ""
            choices.append({"pk": pk, "name": name})
        return choices

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
            if field_name == self.CREDIT_PERSON_UI_FIELD or getattr(
                Comic._meta.get_field(field_name), "remote_field", None
            ):
                if field_name == self.CREDIT_PERSON_UI_FIELD:
                    # The only deep relation choice
                    rel = "credits__person"
                else:
                    rel = field_name

                choices = self._get_m2m_field_choices(rel, comic_qs)
            else:
                choices = self._get_field_choices(field_name, comic_qs)

            if len(choices) > 1:
                # only offer choices when there's more than one choice.
                data[field_name] = choices

        serializer = self.get_serializer(data)
        return Response(serializer.data)

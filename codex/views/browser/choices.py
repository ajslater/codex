"""View for marking comics read and unread."""
import pycountry

from drf_spectacular.utils import extend_schema
from rest_framework.response import Response

from codex.models import Comic, CreditPerson
from codex.serializers.browser import BrowserChoicesSerializer
from codex.serializers.models import PyCountrySerializer
from codex.settings.logging import get_logger
from codex.views.auth import IsAuthenticatedOrEnabledNonUsers
from codex.views.browser.base import BrowserBaseView


LOG = get_logger(__name__)


class BrowserChoiceView(BrowserBaseView):
    """Get choices for filter dialog."""

    permission_classes = [IsAuthenticatedOrEnabledNonUsers]
    serializer_class = BrowserChoicesSerializer

    _PYCOUNTRY_FIELDS = ("country", "language")

    @classmethod
    def _get_remote_fields(cls, remote_field, comic_qs):
        """Use a model serializer."""
        model = remote_field.model
        qs = model.objects.filter(comic__in=comic_qs).distinct().values("pk", "name")

        return qs

    @staticmethod
    def _get_credit_persons(comic_qs):
        """Serialize this special double remote relationship."""
        qs = (
            CreditPerson.objects.filter(credit__comic__in=comic_qs)
            .distinct()
            .values("pk", "name")
        )
        return qs

    def get_object(self):
        """Get the comic subquery use for the choices."""
        object_filter, _ = self.get_query_filters(True, True)
        return Comic.objects.filter(object_filter)

    def _serialize_pycounty_field(self, field_name, comic_qs):
        """Create a pk:name object for fields without tables."""
        qs = []

        if field_name == "country":
            lookup = pycountry.countries
        elif field_name == "language":
            lookup = pycountry.languages
        else:
            return qs

        vals = comic_qs.values_list(field_name, flat=True).distinct()
        for val in vals:
            name = PyCountrySerializer.lookup_name(lookup, val)
            qs.append({"pk": val, "name": name})

        return qs

    @extend_schema(request=BrowserBaseView.input_serializer_class)
    def get(self, request, *args, **kwargs):
        """Get choices for filter dialog."""
        self.parse_params()
        comic_qs = self.get_object()

        field_name = self.kwargs.get("field_name")
        if field_name == self.CREDIT_PERSON_UI_FIELD:
            qs = self._get_credit_persons(comic_qs)
        else:
            field = Comic._meta.get_field(field_name)
            remote_field = getattr(field, "remote_field", None)

            if remote_field:
                qs = self._get_remote_fields(remote_field, comic_qs)
            else:
                qs = self._serialize_pycounty_field(field_name, comic_qs)

        serializer = self.get_serializer(qs, many=True, read_only=True)
        return Response(serializer.data)

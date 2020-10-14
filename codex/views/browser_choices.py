"""View for marking comics read and unread."""
import logging

from django.http import Http404
from rest_framework.response import Response

import codex.serializers.models

from codex.models import Comic
from codex.models import CreditPerson
from codex.serializers.models import CreditPersonSerializer
from codex.views.auth import IsAuthenticatedOrEnabledNonUsers
from codex.views.browser_base import BrowserBaseView


LOG = logging.getLogger(__name__)


class BrowserChoiceView(BrowserBaseView):
    """Get choices for filter dialog."""

    permission_classes = [IsAuthenticatedOrEnabledNonUsers]

    PYCOUNTRY_FIELDS = ("country", "language")

    @staticmethod
    def serialize(name, qs):
        """Find a serializer class by name and serialize the queryset."""
        try:
            class_name = name + "Serializer"
            serializer_class = getattr(codex.serializers.models, class_name)
        except AttributeError as exc:
            LOG.error(exc)
            raise Http404(f"Filter for {name} not found")
        serializer = serializer_class(qs, many=True, read_only=True)
        return serializer.data

    @classmethod
    def serialize_remote_field(cls, remote_field, comic_qs, field_name):
        """Use a model serializer."""
        model = remote_field.model
        qs = model.objects.filter(comic__in=comic_qs).distinct().values("pk", "name")

        return cls.serialize(model.__name__, qs)

    @staticmethod
    def serialize_credit_person(comic_qs):
        """Serialize this special double remote relationship."""
        qs = (
            CreditPerson.objects.filter(credit__comic__in=comic_qs)
            .distinct()
            .values("pk", "name")
        )
        serializer = CreditPersonSerializer(qs, many=True, read_only=True)
        return serializer.data

    def get(self, request, *args, **kwargs):
        """Get choices for filter dialog."""
        self.params = self.get_session(self.BROWSER_KEY)

        object_filter, _ = self.get_query_filters(True)
        comic_qs = Comic.objects.filter(object_filter)

        field_name = self.kwargs.get("field_name")
        if field_name == self.CREDIT_PERSON_UI_FIELD:
            data = self.serialize_credit_person(comic_qs)
        else:
            field = Comic._meta.get_field(field_name)
            remote_field = getattr(field, "remote_field", None)

            if remote_field:
                data = self.serialize_remote_field(remote_field, comic_qs, field_name)
            else:
                data = comic_qs.values_list(field_name, flat=True).distinct()
                if field_name in self.PYCOUNTRY_FIELDS:
                    # specially serialize pycountry fields
                    data = self.serialize(field_name.capitalize(), data)

        return Response(data)

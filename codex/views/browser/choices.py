"""View for marking comics read and unread."""
from typing import Type

from django.http import Http404
from drf_spectacular.utils import extend_schema
from rest_framework.response import Response
from rest_framework.serializers import Serializer

import codex.serializers.models

from codex.models import Comic, CreditPerson
from codex.serializers.models import CreditPersonSerializer
from codex.settings.logging import get_logger
from codex.views.auth import IsAuthenticatedOrEnabledNonUsers
from codex.views.browser.base import BrowserBaseView


LOG = get_logger(__name__)


def add_spectacular_media_type(responses, cls):
    responses[
        (200, "application/json+" + cls.__name__.removesuffix("Serializer"))
    ] = cls


def compute_all_responses():
    responses = {}
    add_spectacular_media_type(responses, CreditPersonSerializer)
    for field in Comic._meta.get_fields():
        if remote_field := getattr(field, "remote_field", None):
            name = remote_field.model.__name__ + "Serializer"
            if serializer_class := getattr(codex.serializers.models, name, None):
                add_spectacular_media_type(responses, serializer_class)
    responses = dict(sorted(responses.items()))
    return responses


RESPONSES = compute_all_responses()


class BrowserChoiceView(BrowserBaseView):
    """Get choices for filter dialog."""

    permission_classes = [IsAuthenticatedOrEnabledNonUsers]

    _PYCOUNTRY_FIELDS = ("country", "language")

    @staticmethod
    def _serialize(name, qs):
        """Find a serializer class by name and serialize the queryset."""
        try:
            class_name = name + "Serializer"
            serializer_class = getattr(codex.serializers.models, class_name)
        except AttributeError as exc:
            LOG.error(exc)
            raise Http404(f"Filter for {name} not found") from exc
        serializer = serializer_class(qs, many=True, read_only=True)
        return serializer.data

    @classmethod
    def _serialize_remote_field(cls, remote_field, comic_qs):
        """Use a model serializer."""
        model = remote_field.model
        qs = model.objects.filter(comic__in=comic_qs).distinct().values("pk", "name")

        return cls._serialize(model.__name__, qs)

    @staticmethod
    def _serialize_credit_person(comic_qs):
        """Serialize this special double remote relationship."""
        qs = (
            CreditPerson.objects.filter(credit__comic__in=comic_qs)
            .distinct()
            .values("pk", "name")
        )
        serializer = CreditPersonSerializer(qs, many=True, read_only=True)
        return serializer.data

    def get_object(self):
        object_filter, _ = self.get_query_filters(True, True)
        return Comic.objects.filter(object_filter)

    @extend_schema(request=BrowserBaseView.input_serializer_class, responses=RESPONSES)
    def get(self, request, *args, **kwargs):
        """Get choices for filter dialog."""
        self.parse_params()
        comic_qs = self.get_object()

        # TODO can i use a regular serializer for this? it's crazy.
        field_name = self.kwargs.get("field_name")
        if field_name == self.CREDIT_PERSON_UI_FIELD:
            data = self._serialize_credit_person(comic_qs)
        else:
            field = Comic._meta.get_field(field_name)
            remote_field = getattr(field, "remote_field", None)

            if remote_field:
                data = self._serialize_remote_field(remote_field, comic_qs)
            else:
                data = comic_qs.values_list(field_name, flat=True).distinct()
                if field_name in self._PYCOUNTRY_FIELDS:
                    # specially serialize pycountry fields
                    data = self._serialize(field_name.capitalize(), data)

        return Response(data)

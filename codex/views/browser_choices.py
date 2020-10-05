"""View for marking comics read and unread."""
import logging

from django.http import Http404
from rest_framework.response import Response

import codex.serializers.models

from codex.models import Comic
from codex.views.auth import IsAuthenticatedOrEnabledNonUsers
from codex.views.browser_base import BrowserBaseView


LOG = logging.getLogger(__name__)


class BrowserChoiceView(BrowserBaseView):
    """Get choices for filter dialog."""

    permission_classes = [IsAuthenticatedOrEnabledNonUsers]

    @staticmethod
    def get_remote_field_data(remote_field, comic_qs, field_name):
        """Use a model serializer."""
        model = remote_field.model
        qs = model.objects.filter(comic__in=comic_qs).distinct().values("pk", "name")

        try:
            class_name = model.__name__ + "Serializer"
            serializer_class = getattr(codex.serializers.models, class_name)
        except AttributeError as exc:
            LOG.error(exc)
            raise Http404(f"Filter for {field_name} not found")
        serializer = serializer_class(qs, many=True, read_only=True)
        return serializer.data

    def get(self, request, *args, **kwargs):
        """Get choices for filter dialog."""
        field_name = self.kwargs.get("field_name")

        self.params = self.get_session(self.BROWSER_KEY)

        filters, _ = self.get_query_filters(True)
        comic_qs = Comic.objects.filter(filters)

        field = Comic._meta.get_field(field_name)
        remote_field = getattr(field, "remote_field", None)

        if remote_field:
            data = self.get_remote_field_data(remote_field, comic_qs, field_name)
        else:
            data = comic_qs.values_list(field_name, flat=True).distinct()

        return Response(data)

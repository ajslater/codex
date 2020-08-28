"""View for marking comics read and unread."""
import logging

from django.http import Http404
from rest_framework.response import Response

import codex.choices.model

from codex.models import Comic
from codex.serializers.vuetify import VueIntChoiceSerializer
from codex.views.browse_base import BrowseBaseView


LOG = logging.getLogger(__name__)


class BrowseChoiceView(BrowseBaseView):
    """Get choices for filter dialog."""

    def get(self, request, *args, **kwargs):
        """Get choices for filter dialog."""
        choice_type = self.kwargs.get("choice_type")

        self.params = self.get_session(self.BROWSE_KEY)

        filters, _ = self.get_query_filters(True)

        choices_comic_list = (
            Comic.objects.filter(filters)
            .only(choice_type)
            .prefetch_related(choice_type)
        )

        class_name = f"{choice_type.capitalize()}FilterChoice"
        try:
            choices_class = getattr(codex.choices.model, class_name)
        except AttributeError as exc:
            LOG.error(exc)
            raise Http404(f"Filter for {choice_type} not found")
        choices = choices_class.get_vue_choices(choices_comic_list)

        serializer = VueIntChoiceSerializer(choices, many=True, read_only=True)
        return Response(serializer.data)

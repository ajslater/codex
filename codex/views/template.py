"""Generic Codex Template View."""

from collections.abc import Sequence

from rest_framework import status
from rest_framework.renderers import BaseRenderer, TemplateHTMLRenderer
from rest_framework.response import Response
from rest_framework.views import APIView


class TemplateXMLRenderer(TemplateHTMLRenderer):
    """Template rendeerer for xml."""

    media_type = "text/xml"
    format = "xml"


class CodexAPIView(APIView):
    """APIView with a simple getter and no data."""

    content_type = "application/json"
    status_code = status.HTTP_200_OK

    def get(self, *args, **kwargs):
        """Render the template with correct content_type."""
        return Response(
            data={}, status=self.status_code, content_type=self.content_type
        )


class CodexTemplateView(CodexAPIView):
    """HTML Template View."""

    renderer_classes: Sequence[type[BaseRenderer]] = (TemplateHTMLRenderer,)

    content_type = "text/html"


class CodexXMLTemplateMixin:
    """XML Template View."""

    renderer_classes: Sequence[type[BaseRenderer]] = (TemplateXMLRenderer,)

    content_type = "application/xml"

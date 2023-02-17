"""Specialized Homepage API."""
from caseconverter import snakecase
from rest_framework.generics import GenericAPIView
from rest_framework.response import Response

from codex.models import Comic, Publisher, Series
from codex.permissions import HasAPIKey
from codex.serializers.homepage import HomepageSerializer


class HomepageStatsView(GenericAPIView):
    """Admin Flag Viewset."""

    permission_classes = [HasAPIKey]
    serializer_class = HomepageSerializer

    _GROUP_MODELS = (
        Publisher,
        Series,
        Comic,
    )

    @staticmethod
    def _get_model_counts(models):
        """Get database counts of each model group."""
        obj = {}
        for model in models:
            key = snakecase(model.__name__) + "_count"
            obj[key] = model.objects.count()
        return obj

    @classmethod
    def get_object(cls):
        """Construct the stats object."""
        obj = cls._get_model_counts(cls._GROUP_MODELS)
        return obj

    def get(self, request, *args, **kwargs):
        """Get the stats object and serialize it."""
        obj = self.get_object()
        serializer = self.get_serializer(obj)
        return Response(serializer.data)

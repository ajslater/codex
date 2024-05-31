"""Admin Auth."""

from rest_framework.generics import GenericAPIView
from rest_framework.parsers import JSONParser
from rest_framework.permissions import IsAdminUser
from rest_framework.views import APIView
from rest_framework.viewsets import ModelViewSet, ReadOnlyModelViewSet


class AdminAuthMixin:
    """Admin Authorization Classes."""

    parser_classes = (JSONParser,)
    permission_classes = (IsAdminUser,)


class AdminAPIView(AdminAuthMixin, APIView):
    """Admin API View."""


class AdminGenericAPIView(AdminAuthMixin, GenericAPIView):
    """Admin Generic API View."""


class AdminModelViewSet(AdminAuthMixin, ModelViewSet):
    """Admin Model View Set."""


class AdminReadOnlyModelViewSet(AdminAuthMixin, ReadOnlyModelViewSet):
    """Admin Read Only Model View Set."""

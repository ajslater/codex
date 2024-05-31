"""Admin Auth."""

from rest_framework.generics import GenericAPIView
from rest_framework.permissions import IsAdminUser
from rest_framework.views import APIView
from rest_framework.viewsets import ModelViewSet, ReadOnlyModelViewSet


class AdminAuthMixin:
    """Admin Authorization Classes."""

    permission_classes = (IsAdminUser,)


class AdminAPIView(APIView, AdminAuthMixin):
    """Admin API View."""


class AdminGenericAPIView(GenericAPIView, AdminAuthMixin):
    """Admin Generic API View."""


class AdminModelViewSet(ModelViewSet, AdminAuthMixin):
    """Admin Model View Set."""


class AdminReadOnlyModelViewSet(ReadOnlyModelViewSet, AdminAuthMixin):
    """Admin Read Only Model View Set."""

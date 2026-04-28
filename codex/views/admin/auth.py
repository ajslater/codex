"""Admin Auth."""

from collections.abc import Sequence
from typing import ClassVar

from rest_framework.generics import GenericAPIView
from rest_framework.permissions import IsAdminUser, _PermissionClass
from rest_framework.views import APIView
from rest_framework.viewsets import ModelViewSet, ReadOnlyModelViewSet


class AdminAuthMixin:
    """Admin Authorization Classes."""

    permission_classes: ClassVar[Sequence[_PermissionClass]] = (IsAdminUser,)


class AdminAPIView(AdminAuthMixin, APIView):
    """Admin API View."""


class AdminGenericAPIView(AdminAuthMixin, GenericAPIView):
    """Admin Generic API View."""


class AdminModelViewSet(AdminAuthMixin, ModelViewSet):
    """Admin Model View Set."""


class AdminReadOnlyModelViewSet(AdminAuthMixin, ReadOnlyModelViewSet):
    """Admin Read Only Model View Set."""

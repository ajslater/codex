"""Admin Auth."""

from collections.abc import Sequence
from typing import TYPE_CHECKING, ClassVar

from adrf.generics import GenericAPIView as AsyncGenericAPIView
from adrf.viewsets import ReadOnlyModelViewSet as AsyncReadOnlyModelViewSet
from rest_framework.generics import GenericAPIView
from rest_framework.permissions import IsAdminUser
from rest_framework.views import APIView
from rest_framework.viewsets import ModelViewSet, ReadOnlyModelViewSet

if TYPE_CHECKING:
    # _PermissionClass exists only in djangorestframework-stubs, not at runtime.
    from rest_framework.permissions import _PermissionClass


class AdminAuthMixin:
    """Admin Authorization Classes."""

    permission_classes: ClassVar[Sequence["_PermissionClass"]] = (IsAdminUser,)


class AdminAPIView(AdminAuthMixin, APIView):
    """Admin API View."""


class AdminGenericAPIView(AdminAuthMixin, GenericAPIView):
    """Admin Generic API View."""


class AdminModelViewSet(AdminAuthMixin, ModelViewSet):
    """Admin Model View Set."""


class AdminReadOnlyModelViewSet(AdminAuthMixin, ReadOnlyModelViewSet):
    """Admin Read Only Model View Set."""


class AsyncAdminGenericAPIView(AdminAuthMixin, AsyncGenericAPIView):
    """Admin Generic API View dispatched on the asyncio event loop."""

    view_is_async = True


class AsyncAdminReadOnlyModelViewSet(AdminAuthMixin, AsyncReadOnlyModelViewSet):
    """Admin Read Only Model View Set dispatched on the asyncio event loop."""

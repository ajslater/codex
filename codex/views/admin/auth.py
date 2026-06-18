"""
Admin Auth + wire-format mixins.

Resource viewsets render JSON:API; action endpoints (APIView,
GenericAPIView, async views) render the envelope. Both pick up
cursor pagination, which is harmless for non-list endpoints.
"""

from collections.abc import Sequence
from typing import TYPE_CHECKING, ClassVar

from adrf.generics import GenericAPIView as AsyncGenericAPIView
from adrf.viewsets import ReadOnlyModelViewSet as AsyncReadOnlyModelViewSet
from rest_framework.generics import GenericAPIView
from rest_framework.permissions import IsAdminUser
from rest_framework.views import APIView
from rest_framework.viewsets import ModelViewSet, ReadOnlyModelViewSet

from codex.views.admin.json_api import AdminEnvelopeMixin, AdminJsonApiMixin

if TYPE_CHECKING:
    # _PermissionClass exists only in djangorestframework-stubs, not at runtime.
    from rest_framework.permissions import _PermissionClass


class AdminAuthMixin:
    """Admin Authorization Classes."""

    permission_classes: ClassVar[Sequence["_PermissionClass"]] = (IsAdminUser,)


class AdminAPIView(AdminEnvelopeMixin, AdminAuthMixin, APIView):
    """Admin API View."""


class AdminGenericAPIView(AdminEnvelopeMixin, AdminAuthMixin, GenericAPIView):
    """Admin Generic API View."""


class AdminModelViewSet(AdminJsonApiMixin, AdminAuthMixin, ModelViewSet):
    """Admin Model View Set."""


class AdminReadOnlyModelViewSet(
    AdminJsonApiMixin, AdminAuthMixin, ReadOnlyModelViewSet
):
    """Admin Read Only Model View Set."""


class AsyncAdminGenericAPIView(AdminEnvelopeMixin, AdminAuthMixin, AsyncGenericAPIView):
    """Admin Generic API View dispatched on the asyncio event loop."""

    view_is_async = True


class AsyncAdminReadOnlyModelViewSet(
    AdminEnvelopeMixin, AdminAuthMixin, AsyncReadOnlyModelViewSet
):
    """Admin Read Only Model View Set dispatched on the asyncio event loop."""

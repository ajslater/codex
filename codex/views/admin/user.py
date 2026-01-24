"""Admin User ViewSet."""

from django.contrib.auth.models import User
from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError
from rest_framework.authtoken.models import Token
from rest_framework.response import Response
from rest_framework.status import HTTP_202_ACCEPTED, HTTP_400_BAD_REQUEST
from typing_extensions import override

from codex.choices.notifications import Notifications
from codex.librarian.mp_queue import LIBRARIAN_QUEUE
from codex.librarian.notifier.tasks import (
    ADMIN_USERS_CHANGED_TASK,
    USERS_CHANGED_TASK,
    NotifierTask,
)
from codex.serializers.admin.users import UserChangePasswordSerializer, UserSerializer
from codex.views.admin.auth import AdminGenericAPIView, AdminModelViewSet

_BAD_CURRENT_USER_FALSE_KEYS = ("is_active", "is_staff", "is_superuser")


class AdminUserViewSet(AdminModelViewSet):
    """User ViewSet."""

    queryset = (
        User.objects.prefetch_related("groups")
        .select_related("useractive")
        .defer("first_name", "last_name", "email")
    )
    serializer_class = UserSerializer
    INPUT_METHODS = ("POST", "PUT")

    @staticmethod
    def _on_change(uid: int):
        if uid:
            group = f"user_{uid}"
            tasks = (
                ADMIN_USERS_CHANGED_TASK,
                NotifierTask(Notifications.USERS.value, group),
            )
        else:
            tasks = (USERS_CHANGED_TASK,)
        for task in tasks:
            LIBRARIAN_QUEUE.put(task)

    @override
    def get_serializer(self, *args, **kwargs):
        """Allow partial data for update methods."""
        if self.request.method in self.INPUT_METHODS:
            kwargs["partial"] = True
        return super().get_serializer(*args, **kwargs)

    def _is_change_to_current_user(self):
        instance = self.get_object()
        return instance == self.request.user

    @override
    def destroy(self, request, *args, **kwargs):
        """Destroy with guard for logged in user."""
        if self._is_change_to_current_user():
            reason = "Cannot delete logged in user."
            raise ValidationError(reason)
        res = super().destroy(request, *args, **kwargs)
        self._on_change(0)
        return res

    @override
    def perform_update(self, serializer):
        """Add hook after update."""
        data = serializer.validated_data
        if self._is_change_to_current_user() and False in {
            data.get(key) for key in _BAD_CURRENT_USER_FALSE_KEYS
        }:
            reason = "Cannot deactivate logged in user."
            raise ValidationError(reason)
        uid = self.kwargs.get("pk", 0)
        super().perform_update(serializer)
        self._on_change(uid)

    @override
    def perform_create(self, serializer):
        """Create user."""
        validated_data = serializer.validated_data
        password = validated_data["password"]
        validate_password(password)
        groups = validated_data.pop("groups")
        validated_data["email"] = ""
        user = User.objects.create_user(**validated_data)
        if groups:
            user.groups.set(groups)
            user.save()
        Token.objects.create(user=user)


class AdminUserChangePasswordView(AdminGenericAPIView):
    """Special View to hash user password."""

    serializer_class = UserChangePasswordSerializer

    def put(self, request, *args, **kwargs):
        """Validate and set the user password."""
        try:
            serializer = self.get_serializer(data=request.data)
            serializer.is_valid(raise_exception=True)
            pk = self.kwargs["pk"]
            user = User.objects.get(pk=pk)

            password = serializer.validated_data["password"]
            validate_password(password, user=user)

            user.set_password(password)
            user.save()
            status = HTTP_202_ACCEPTED
            detail = "Successfully changed password"
        except ValidationError as exc:
            status = HTTP_400_BAD_REQUEST
            detail = exc.error_list

        return Response(
            status=status,
            data={"detail": detail},
        )

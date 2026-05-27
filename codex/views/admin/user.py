"""Admin User ViewSet."""

from typing import override

from django.contrib.auth.models import User
from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError
from rest_framework.authtoken.models import Token
from rest_framework.exceptions import ValidationError as DRFValidationError
from rest_framework.response import Response
from rest_framework.status import (
    HTTP_200_OK,
    HTTP_202_ACCEPTED,
    HTTP_400_BAD_REQUEST,
    HTTP_404_NOT_FOUND,
    HTTP_409_CONFLICT,
)
from rest_registration.settings import registration_settings

from codex.choices.admin import AdminFlagChoices
from codex.librarian.mp_queue import LIBRARIAN_QUEUE
from codex.librarian.notifier.tasks import users_changed_task
from codex.models import AdminFlag
from codex.models.auth import UserAuth
from codex.serializers.admin.users import UserChangePasswordSerializer, UserSerializer
from codex.settings.db import email_enabled
from codex.views.admin.auth import AdminAPIView, AdminGenericAPIView, AdminModelViewSet

_BAD_CURRENT_USER_FALSE_KEYS = ("is_active", "is_staff", "is_superuser")


class AdminUserViewSet(AdminModelViewSet):
    """User ViewSet."""

    queryset = (
        User.objects.prefetch_related("groups")
        .select_related("userauth__age_rating_metron")
        .defer("first_name", "last_name")
    )
    serializer_class = UserSerializer
    INPUT_METHODS = ("POST", "PUT")

    @staticmethod
    def _on_change(uid: int) -> None:
        if uid:
            # User-targeted change: send to that user's private
            # channel plus the ADMIN channel so admin tables refresh.
            tasks = (
                users_changed_task(ids=[uid]),
                users_changed_task(uid=uid, ids=[uid]),
            )
        else:
            # Broadcast change (e.g. bulk delete).
            tasks = (users_changed_task(),)
        for task in tasks:
            LIBRARIAN_QUEUE.put(task)

    @override
    def get_serializer(self, *args, **kwargs):
        """Allow partial data for update methods."""
        if self.request.method in self.INPUT_METHODS:
            kwargs["partial"] = True
        return super().get_serializer(*args, **kwargs)

    def _is_change_to_current_user(self) -> bool:
        instance = self.get_object()
        return instance == self.request.user

    @override
    def destroy(self, request, *args, **kwargs) -> Response:
        """Destroy with guard for logged in user."""
        if self._is_change_to_current_user():
            reason = "Cannot delete logged in user."
            raise ValidationError(reason)
        res = super().destroy(request, *args, **kwargs)
        self._on_change(0)
        return res

    @override
    def perform_update(self, serializer) -> None:
        """Add hook after update."""
        data = serializer.validated_data
        if not data.get("password"):
            data.pop("password", None)
        if self._is_change_to_current_user() and any(
            data.get(key) is False for key in _BAD_CURRENT_USER_FALSE_KEYS
        ):
            reason = "Cannot deactivate logged in user."
            raise ValidationError(reason)
        uid = self.kwargs.get("pk", 0)
        super().perform_update(serializer)
        self._on_change(uid)

    @override
    def perform_create(self, serializer) -> None:
        """Create user; ``UserAuth`` is provisioned by post_save signal."""
        validated_data = serializer.validated_data
        password = validated_data["password"]
        # Django's ``validate_password`` raises a Django (not DRF)
        # ``ValidationError`` which DRF's default exception handler does
        # not convert to a 400 — it would propagate as a 500. Re-raise
        # as a DRF field error so the create dialog renders the message
        # inline next to the Password input.
        try:
            validate_password(password)
        except ValidationError as exc:
            raise DRFValidationError({"password": list(exc.messages)}) from exc
        groups = validated_data.pop("groups")
        # Pop nested userauth data before handing to create_user; the
        # post_save signal in ``codex.signals.django_signals`` provisions
        # an empty UserAuth row, which we then patch with the
        # admin-supplied ceiling if any.
        userauth_data = validated_data.pop("userauth", {})
        validated_data.setdefault("email", "")
        user = User.objects.create_user(**validated_data)
        if groups:
            user.groups.set(groups)
            user.save()
        Token.objects.create(user=user)
        if "age_rating_metron" in userauth_data:
            UserAuth.objects.filter(user=user).update(
                age_rating_metron=userauth_data["age_rating_metron"],
            )
        # ``CreateModelMixin.create`` reads ``serializer.data`` after
        # perform_create returns to build the 201 response body. With
        # ``serializer.instance`` unset (we bypass ``serializer.save``
        # so we can wire ``UserAuth`` via the post_save signal),
        # ``serializer.data`` falls back to ``validated_data`` — a dict
        # that ``userauth.*`` source-attr fields cannot traverse,
        # raising ``KeyError: 'userauth'``. Attach the saved User so
        # the response serializes against the real instance.
        serializer.instance = user


class AdminUserSendVerificationView(AdminAPIView):
    """
    Resend the registration-verification email for an inactive user.

    Mirrors the same ``REGISTER_VERIFICATION_EMAIL_SENDER`` callable that
    the public register flow uses, so the link the admin triggers is
    identical to the one rest-registration would have sent at signup
    time. Requirements (any failure returns a structured error):

    * Email backend is configured (``email_enabled`` consults the
      EmailSettings singleton then TOML/env).
    * The ``Verify New User Email`` admin flag (``RV``) is on — this is
      a site policy switch, so the admin-action surface honors it
      rather than silently overriding.
    * The target user is inactive (``is_active=False``); already-active
      users have nothing to verify.
    * The user has an email address on file.
    """

    def post(self, _request, pk: int) -> Response:
        """Send the verification email to the given user."""
        if not email_enabled():
            return Response(
                {"detail": "Email is not configured."},
                status=HTTP_400_BAD_REQUEST,
            )
        rv_on = AdminFlag.objects.filter(
            key=AdminFlagChoices.REGISTER_VERIFICATION.value, on=True
        ).exists()
        if not rv_on:
            return Response(
                {"detail": "Verify New User Email is off."},
                status=HTTP_400_BAD_REQUEST,
            )
        try:
            user = User.objects.get(pk=pk)
        except User.DoesNotExist:
            return Response({"detail": "User not found."}, status=HTTP_404_NOT_FOUND)
        if user.is_active:
            return Response(
                {"detail": "User is already active."},
                status=HTTP_409_CONFLICT,
            )
        if not user.email:
            return Response(
                {"detail": "User has no email address."},
                status=HTTP_400_BAD_REQUEST,
            )
        email_sender = registration_settings.REGISTER_VERIFICATION_EMAIL_SENDER
        email_sender(self.request, user)
        return Response(
            {"detail": f"Verification email sent to {user.email}."},
            status=HTTP_200_OK,
        )


class AdminUserChangePasswordView(AdminGenericAPIView):
    """Special View to hash user password."""

    serializer_class = UserChangePasswordSerializer

    def put(self, request, *args, **kwargs) -> Response:
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

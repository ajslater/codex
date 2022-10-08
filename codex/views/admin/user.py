"""Admin User ViewSet."""
from django.contrib.auth.models import User
from django.contrib.auth.password_validation import validate_password
from django.core.cache import cache
from django.core.exceptions import ValidationError
from rest_framework.generics import GenericAPIView
from rest_framework.permissions import IsAdminUser
from rest_framework.response import Response
from rest_framework.status import HTTP_202_ACCEPTED, HTTP_400_BAD_REQUEST
from rest_framework.viewsets import ModelViewSet

from codex.librarian.queue_mp import LIBRARIAN_QUEUE
from codex.notifier.tasks import LIBRARY_CHANGED_TASK
from codex.serializers.admin import UserChangePasswordSerializer, UserSerializer
from codex.settings.logging import get_logger


LOG = get_logger(__name__)


class AdminUserViewSet(ModelViewSet):
    """User ViewSet."""

    permission_classes = [IsAdminUser]
    queryset = User.objects.prefetch_related("groups").defer(
        "first_name", "last_name", "email"
    )
    serializer_class = UserSerializer
    INPUT_METHODS = ("POST", "PUT")

    @staticmethod
    def _on_change():
        cache.clear()
        LIBRARIAN_QUEUE.put(LIBRARY_CHANGED_TASK)

    def get_serializer(self, *args, **kwargs):
        """Allow partial data for update methods."""
        if self.request.method in self.INPUT_METHODS:
            kwargs["partial"] = True
        return super().get_serializer(*args, **kwargs)

    def destroy(self, request, *args, **kwargs):
        """Destroy with guard for logged in user."""
        instance = self.get_object()
        if instance == request.user:
            raise ValueError("Cannot delete logged in user.")
        return super().destroy(request, *args, **kwargs)

    def perform_update(self, serializer):
        """Add hook after update."""
        super().perform_update(serializer)
        self._on_change()


class AdminUserChangePasswordView(GenericAPIView):
    """Special View to hash user password."""

    permission_classes = [IsAdminUser]
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

"""Throttled wrappers for rest-registration's reset-password views."""

from rest_framework.throttling import ScopedRateThrottle
from rest_registration.api.views.reset_password import (
    ResetPasswordView as _ResetPasswordView,
)
from rest_registration.api.views.reset_password import (
    SendResetPasswordLinkView as _SendResetPasswordLinkView,
)


class SendResetPasswordLinkView(_SendResetPasswordLinkView):
    """Rate-limited variant; the rate is set via the ``reset_password`` scope."""

    throttle_classes = (ScopedRateThrottle,)
    throttle_scope = "reset_password"


class ResetPasswordView(_ResetPasswordView):
    """Rate-limited variant; the rate is set via the ``reset_password`` scope."""

    throttle_classes = (ScopedRateThrottle,)
    throttle_scope = "reset_password"

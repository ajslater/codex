"""HTTP-level tests for the password-reset + register-verification flow."""

from typing import Final, override

from django.contrib.auth.models import User
from django.core import mail
from django.core.cache import cache
from django.test import Client, TestCase, override_settings
from django.urls import resolve
from rest_registration.signers.reset_password import ResetPasswordSigner

from codex.choices.admin import AdminFlagChoices
from codex.models import AdminFlag

_TEST_PASSWORD: Final = "test-pw-hush-S106"  # noqa: S105
_NEW_PASSWORD: Final = "new-pw-hush-S106"  # noqa: S105
_TEST_EMAIL: Final = "alice@example.com"

_SESSION_URL: Final = "/api/v4/session"
_SEND_RESET_URL: Final = "/api/v4/auth/password/reset"
_RESET_URL: Final = "/api/v4/auth/password/reset/confirm"
_PROFILE_URL: Final = "/api/v4/auth/profile"
_REGISTER_URL: Final = "/api/v4/auth/register"


def _v4(response):
    """Unwrap the v4 ``{data, meta, errors}`` envelope and return ``data``."""
    body = response.json()
    if isinstance(body, dict) and "data" in body and "meta" in body:
        return body["data"]
    return body


_HTTP_OK: Final = 200
_HTTP_CREATED: Final = 201
_HTTP_BAD_REQUEST: Final = 400
_HTTP_NOT_FOUND: Final = 404


# Mirrors what the settings module computes when [email] is configured.
# Used in @override_settings to flip the feature on for individual tests.
_EMAIL_ON_REST_REGISTRATION = {
    "REGISTER_VERIFICATION_ENABLED": True,
    "REGISTER_EMAIL_VERIFICATION_ENABLED": False,
    "RESET_PASSWORD_VERIFICATION_ENABLED": True,
    "REGISTER_VERIFICATION_URL": "/auth/verify-registration/",
    "RESET_PASSWORD_VERIFICATION_URL": "/auth/reset-password/",
    "RESET_PASSWORD_VERIFICATION_AUTO_LOGIN": False,
    "RESET_PASSWORD_VERIFICATION_ONE_TIME_USE": True,
    "RESET_PASSWORD_FAIL_WHEN_USER_NOT_FOUND": False,
    "RESET_PASSWORD_VERIFICATION_EMAIL_TEMPLATES": {
        "subject": "rest_registration/reset_password/subject.txt",
        "text_body": "rest_registration/reset_password/body.txt",
        "html_body": "rest_registration/reset_password/body.html",
    },
    "VERIFICATION_FROM_EMAIL": "codex@example.com",
    "USER_LOGIN_FIELDS": ("username", "email"),
    "USER_EDITABLE_FIELDS": ("username", "email"),
    "PROFILE_SERIALIZER_CLASS": "codex.serializers.auth.CodexProfileSerializer",
    "USER_HIDDEN_FIELDS": (
        "last_login",
        "is_active",
        "user_permissions",
        "groups",
        "date_joined",
        "first_name",
        "last_name",
    ),
}


def _ensure_admin_flags() -> None:
    """
    Seed every AdminFlag row tests rely on.

    Tests run migrations but skip startup hooks (codex_init), so the
    AdminFlag rows that startup normally creates may be absent. The
    v4 ``/api/v4/session`` permission pipeline ``.get()``s the
    ``NON_USERS`` flag *and* a ``Timestamp`` row for ``CODEX_VERSION``
    — defer to the same seeders ``codex.startup`` calls so every
    choice row exists.
    """
    from codex.startup import init_admin_flags, init_timestamps

    init_admin_flags()
    init_timestamps()
    AdminFlag.objects.filter(key=AdminFlagChoices.REGISTRATION.value).update(on=True)
    AdminFlag.objects.filter(key=AdminFlagChoices.REGISTER_VERIFICATION.value).update(
        on=False
    )


class ResetPasswordRouteTests(TestCase):
    """The emailed reset link must reach the SPA, not the catch-all redirect."""

    def test_reset_password_path_resolves_to_spa_index(self) -> None:
        """
        ``/auth/reset-password/`` resolves to the SPA index view.

        Regression: the path was not enumerated in the app urlconf, so it
        fell through to the catch-all ``RedirectView`` and 302'd the emailed
        link to the home page — the reset screen never rendered.
        """
        match = resolve("/auth/reset-password/")
        assert match.view_name == "app:reset-password"


class PasswordResetDisabledTests(TestCase):
    """Default install (no [email] block) keeps the feature off."""

    @override
    def setUp(self) -> None:
        """Seed the AdminFlag rows the v4 session endpoint requires."""
        _ensure_admin_flags()

    def test_flags_report_email_disabled(self) -> None:
        """``/api/v4/session`` reports ``adminFlags.emailEnabled: false`` by default."""
        response = self.client.get(_SESSION_URL)
        assert response.status_code == _HTTP_OK
        assert _v4(response)["adminFlags"]["emailEnabled"] is False

    def test_send_reset_link_404(self) -> None:
        """``send-reset-password-link/`` 404s when feature is off."""
        response = self.client.post(
            _SEND_RESET_URL, data={"login": "anyone"}, content_type="application/json"
        )
        assert response.status_code == _HTTP_NOT_FOUND

    def test_reset_password_404(self) -> None:
        """``reset-password/`` 404s when feature is off."""
        payload = {
            "userId": "1",
            "timestamp": 0,
            "signature": "x",
            "password": _NEW_PASSWORD,
        }
        response = self.client.post(
            _RESET_URL, data=payload, content_type="application/json"
        )
        assert response.status_code == _HTTP_NOT_FOUND


@override_settings(
    EMAIL_ENABLED=True,
    EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend",
    EMAIL_HOST="smtp.example.com",
    DEFAULT_FROM_EMAIL="codex@example.com",
    REST_REGISTRATION=_EMAIL_ON_REST_REGISTRATION,
)
class PasswordResetEnabledTests(TestCase):
    """Reset flow exercises with the feature on and locmem capturing mail."""

    @override
    def setUp(self) -> None:
        """Provision a user with an email and an authenticated client."""
        # ScopedRateThrottle persists hit counts in the Django cache;
        # without an explicit clear, the 5/hour reset_password rate is
        # exhausted across tests in the same class.
        cache.clear()
        _ensure_admin_flags()
        self.user = User.objects.create_user(  # pyright: ignore[reportUninitializedInstanceVariable]
            username="alice",
            password=_TEST_PASSWORD,
            email=_TEST_EMAIL,
        )
        self.client = Client()
        mail.outbox.clear()

    def test_flags_report_email_enabled(self) -> None:
        """Capability flag flips when EMAIL_ENABLED is True."""
        response = self.client.get(_SESSION_URL)
        assert response.status_code == _HTTP_OK
        assert _v4(response)["adminFlags"]["emailEnabled"] is True

    def test_send_reset_link_sends_email_by_username(self) -> None:
        """A valid username produces a reset email containing a signed link."""
        response = self.client.post(
            _SEND_RESET_URL,
            data={"login": "alice"},
            content_type="application/json",
        )
        assert response.status_code == _HTTP_OK
        assert len(mail.outbox) == 1
        body = mail.outbox[0].body
        assert "/auth/reset-password/" in body
        assert "user_id=" in body
        assert "timestamp=" in body
        assert "signature=" in body

    def test_reset_email_link_not_html_escaped(self) -> None:
        """
        The emailed link must use raw ``&`` separators, not ``&amp;``.

        body.txt is a plain-text template; Django autoescaping turns the
        URL's ``&`` into ``&amp;``, which corrupts the query string when the
        link is clicked (the params parse as ``amp;timestamp`` etc.). The
        ``|safe`` filter on ``verification_url`` keeps the URL intact.
        """
        response = self.client.post(
            _SEND_RESET_URL,
            data={"login": "alice"},
            content_type="application/json",
        )
        assert response.status_code == _HTTP_OK
        assert len(mail.outbox) == 1
        body = mail.outbox[0].body
        assert "&amp;" not in body
        assert "&timestamp=" in body
        assert "&signature=" in body

    def test_reset_email_link_includes_username(self) -> None:
        """
        The link carries the username so the reset screen can show it.

        Display-only: the reset is gated by the signed user_id/timestamp/
        signature, never by this param.
        """
        response = self.client.post(
            _SEND_RESET_URL,
            data={"login": "alice"},
            content_type="application/json",
        )
        assert response.status_code == _HTTP_OK
        assert len(mail.outbox) == 1
        assert "&username=alice" in mail.outbox[0].body

    def test_reset_email_is_multipart_with_html_button(self) -> None:
        """
        The reset email ships a styled HTML alternative beside the text body.

        HTML clients render the "Reset Password" button; plain-text readers
        fall back to the text part.
        """
        response = self.client.post(
            _SEND_RESET_URL,
            data={"login": "alice"},
            content_type="application/json",
        )
        assert response.status_code == _HTTP_OK
        assert len(mail.outbox) == 1
        msg = mail.outbox[0]
        # The plain-text part remains the fallback body.
        assert "/auth/reset-password/" in msg.body
        # Exactly one HTML alternative, carrying the button + the signed link.
        html_parts = [c for c, mime in msg.alternatives if mime == "text/html"]  # pyright: ignore[reportAttributeAccessIssue], # ty: ignore[unresolved-attribute]
        assert len(html_parts) == 1
        html = html_parts[0]
        assert "Reset Password" in html
        assert "#cc7b19" in html.lower()  # codex-orange button
        # The link is HTML-escaped in the href but still carries the username.
        assert "&amp;username=alice" in html

    def test_send_reset_link_sends_email_by_email(self) -> None:
        """Email also resolves to the user via USER_LOGIN_FIELDS."""
        response = self.client.post(
            _SEND_RESET_URL,
            data={"login": _TEST_EMAIL},
            content_type="application/json",
        )
        assert response.status_code == _HTTP_OK
        assert len(mail.outbox) == 1

    def test_send_reset_link_does_not_enumerate(self) -> None:
        """Unknown logins return success + no email (no account enumeration)."""
        response = self.client.post(
            _SEND_RESET_URL,
            data={"login": "ghost"},
            content_type="application/json",
        )
        assert response.status_code == _HTTP_OK
        assert mail.outbox == []

    def test_reset_password_happy_path(self) -> None:
        """A valid signature + new password actually changes the password."""
        signer = ResetPasswordSigner({"user_id": self.user.pk})
        signed = signer.get_signed_data()
        response = self.client.post(
            _RESET_URL,
            data={
                "userId": str(signed["user_id"]),
                "timestamp": signed["timestamp"],
                "signature": signed["signature"],
                "password": _NEW_PASSWORD,
            },
            content_type="application/json",
        )
        assert response.status_code == _HTTP_OK, response.content
        self.user.refresh_from_db()
        assert self.user.check_password(_NEW_PASSWORD)

    def test_reset_password_rejects_bad_signature(self) -> None:
        """A tampered signature 400s without touching the password."""
        signer = ResetPasswordSigner({"user_id": self.user.pk})
        signed = signer.get_signed_data()
        response = self.client.post(
            _RESET_URL,
            data={
                "userId": str(signed["user_id"]),
                "timestamp": signed["timestamp"],
                "signature": "tampered",
                "password": _NEW_PASSWORD,
            },
            content_type="application/json",
        )
        assert response.status_code == _HTTP_BAD_REQUEST
        self.user.refresh_from_db()
        assert self.user.check_password(_TEST_PASSWORD)


class ProfileUpdateTests(TestCase):
    """PATCH /auth/profile/ self-service guards."""

    @override
    def setUp(self) -> None:
        """Provision an authenticated user with username + email."""
        self.user = User.objects.create_user(  # pyright: ignore[reportUninitializedInstanceVariable]
            username="bob",
            password=_TEST_PASSWORD,
            email="bob@example.com",
        )
        self.client = Client()
        self.client.force_login(self.user)

    def test_email_update(self) -> None:
        """Self-service email update persists to the DB."""
        response = self.client.patch(
            _PROFILE_URL,
            data={"email": "bob+new@example.com"},
            content_type="application/json",
        )
        assert response.status_code == _HTTP_OK, response.content
        self.user.refresh_from_db()
        assert self.user.email == "bob+new@example.com"

    def test_username_update(self) -> None:
        """Self-service username update persists to the DB."""
        response = self.client.patch(
            _PROFILE_URL,
            data={"username": "bob2"},
            content_type="application/json",
        )
        assert response.status_code == _HTTP_OK, response.content
        self.user.refresh_from_db()
        assert self.user.username == "bob2"

    @override_settings(AUTH_REMOTE_USER=True)
    def test_username_readonly_under_remote_user(self) -> None:
        """With AUTH_REMOTE_USER on, username PATCH is silently ignored."""
        response = self.client.patch(
            _PROFILE_URL,
            data={"username": "bob_renamed"},
            content_type="application/json",
        )
        assert response.status_code == _HTTP_OK, response.content
        self.user.refresh_from_db()
        # Read-only fields are dropped server-side rather than 400'd, which
        # is the standard DRF behaviour. The DB value stays put.
        assert self.user.username == "bob"

    def test_username_collision_rejected(self) -> None:
        """Renaming to a taken username surfaces a 400 from DB uniqueness."""
        User.objects.create_user(username="taken", password=_TEST_PASSWORD)
        response = self.client.patch(
            _PROFILE_URL,
            data={"username": "taken"},
            content_type="application/json",
        )
        assert response.status_code == _HTTP_BAD_REQUEST


class RegisterVerificationTests(TestCase):
    """REGISTER_VERIFICATION AdminFlag gates the verification flow."""

    @override
    def setUp(self) -> None:
        """Open registration and start with verification off."""
        cache.clear()
        _ensure_admin_flags()
        AdminFlag.objects.filter(key=AdminFlagChoices.REGISTRATION.value).update(
            on=True
        )
        AdminFlag.objects.filter(
            key=AdminFlagChoices.REGISTER_VERIFICATION.value
        ).update(on=False)
        self.client = Client()
        mail.outbox.clear()

    def test_register_active_when_flag_off(self) -> None:
        """RV off -> new accounts are active immediately, no email."""
        payload = {
            "username": "carol",
            "email": "carol@example.com",
            "password": _TEST_PASSWORD,
            "passwordConfirm": _TEST_PASSWORD,
        }
        response = self.client.post(
            _REGISTER_URL, data=payload, content_type="application/json"
        )
        assert response.status_code == _HTTP_CREATED, response.content
        user = User.objects.get(username="carol")
        assert user.is_active
        assert mail.outbox == []

    @override_settings(
        EMAIL_ENABLED=True,
        EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend",
        EMAIL_HOST="smtp.example.com",
        DEFAULT_FROM_EMAIL="codex@example.com",
        REST_REGISTRATION=_EMAIL_ON_REST_REGISTRATION,
    )
    def test_register_inactive_when_flag_on(self) -> None:
        """RV on + email enabled -> user is inactive and one verification email is sent."""
        AdminFlag.objects.filter(
            key=AdminFlagChoices.REGISTER_VERIFICATION.value
        ).update(on=True)
        payload = {
            "username": "dave",
            "email": "dave@example.com",
            "password": _TEST_PASSWORD,
            "passwordConfirm": _TEST_PASSWORD,
        }
        response = self.client.post(
            _REGISTER_URL, data=payload, content_type="application/json"
        )
        assert response.status_code == _HTTP_CREATED, response.content
        user = User.objects.get(username="dave")
        assert not user.is_active
        assert len(mail.outbox) == 1

    def test_register_404_when_registration_disabled(self) -> None:
        """Turning the existing REGISTRATION flag off disables the endpoint."""
        AdminFlag.objects.filter(key=AdminFlagChoices.REGISTRATION.value).update(
            on=False
        )
        payload = {
            "username": "eve",
            "email": "eve@example.com",
            "password": _TEST_PASSWORD,
            "passwordConfirm": _TEST_PASSWORD,
        }
        response = self.client.post(
            _REGISTER_URL, data=payload, content_type="application/json"
        )
        assert response.status_code == _HTTP_NOT_FOUND


class AnonymousSessionFlagsTests(TestCase):
    """``/api/v4/session`` must boot logged-out visitors even with non-users off."""

    @override
    def setUp(self) -> None:
        """Seed flags, then require login (non-users OFF) to reproduce the bug."""
        _ensure_admin_flags()
        AdminFlag.objects.filter(key=AdminFlagChoices.NON_USERS.value).update(on=False)

    def test_anonymous_session_ok_when_non_users_off(self) -> None:
        """
        Logged-out + non-users off still returns 200 with the public flags.

        Regression: ``/session`` was gated behind
        ``IsAuthenticatedOrEnabledNonUsers``, so this exact combination
        401'd. The SPA then never received ``registration`` /
        ``nonUsers``, ``isAuthChecked`` stayed false, and the browser
        spun on the placeholder forever.
        """
        response = self.client.get(_SESSION_URL)
        assert response.status_code == _HTTP_OK, response.content
        data = _v4(response)
        # Anonymous payload carries no user but is fully formed.
        assert data["user"] is None
        flags = data["adminFlags"]
        # The public subset the logged-out shell renders.
        assert flags["registration"] is True
        assert flags["nonUsers"] is False
        assert "bannerText" in flags
        assert "registerVerification" in flags
        assert "emailEnabled" in flags
        # Least disclosure: authenticated-only behaviour flags withheld.
        assert "lazyImportMetadata" not in flags
        assert "remoteUserEnabled" not in flags

    def test_authenticated_session_includes_private_flags(self) -> None:
        """An authenticated session additionally sees the private flags."""
        user = User.objects.create_user(username="frank", password=_TEST_PASSWORD)
        self.client.force_login(user)
        response = self.client.get(_SESSION_URL)
        assert response.status_code == _HTTP_OK, response.content
        flags = _v4(response)["adminFlags"]
        assert "lazyImportMetadata" in flags
        assert "remoteUserEnabled" in flags

"""
Tests for native OIDC login: gating, adapter linking, and claim sync.

The OAuth2 handshake itself is allauth's tested territory; these tests
drive ``complete_social_login`` with prebuilt ``SocialLogin`` objects
(what the callback view produces after the token exchange) so every
Codex policy branch is exercised against the real signup/login flows.
"""

from typing import Final, override
from unittest.mock import patch

from allauth.core import context
from allauth.core.exceptions import ImmediateHttpResponse
from allauth.socialaccount.helpers import complete_social_login
from allauth.socialaccount.models import SocialAccount, SocialLogin
from django.contrib.auth.models import AnonymousUser, Group, User
from django.contrib.messages.middleware import MessageMiddleware
from django.contrib.sessions.middleware import SessionMiddleware
from django.core.cache import cache
from django.test import RequestFactory, TestCase
from django.urls import resolve

from codex.models.admin import OIDCSettings
from codex.oidc import (
    DISCOVERY_CACHE_KEY,
    CodexSocialAccountAdapter,
    merged_claims,
    oidc_logout_url,
)
from codex.serializers.auth import ProfileUpdateSerializer
from codex.settings import GRANIAN_URL_PATH_PREFIX

# The test environment configures a url_path_prefix, which conveniently
# proves the error redirects are prefix-qualified.
_SSO_ERROR: Final = f"{GRANIAN_URL_PATH_PREFIX}/auth/sso-error"
_SUB: Final = "sub-1234"
_HTTP_OK: Final = 200
_HTTP_NOT_FOUND: Final = 404
_HTTP_FOUND: Final = 302


def _seed_oidc(**overrides) -> OIDCSettings:
    """Seed the OIDCSettings singleton as a working test deployment."""
    defaults = {
        "enabled": True,
        "provider_name": "Test SSO",
        "server_url": "https://idp.example.com",
        "client_id": "codex-test",
        "client_secret": "test-secret-hush",
        **overrides,
    }
    row, _ = OIDCSettings.objects.update_or_create(pk=1, defaults=defaults)
    return row


def _sociallogin(id_token=None, userinfo=None, sub=_SUB) -> SocialLogin:
    """Build the SocialLogin the callback produces after token exchange."""
    extra_data = {}
    if id_token is not None:
        extra_data["id_token"] = id_token
    if userinfo is not None:
        extra_data["userinfo"] = userinfo
    account = SocialAccount(provider="oidc", uid=sub, extra_data=extra_data)
    sociallogin = SocialLogin(user=User(), account=account)
    data = merged_claims(sociallogin)
    adapter = CodexSocialAccountAdapter()
    request = RequestFactory().get("/sso/oidc/login/callback/")
    adapter.populate_user(request, sociallogin, {"email": data.get("email")})
    return sociallogin


def _request(rf: RequestFactory):
    """Build a request with working session and messages, like the callback's."""
    request = rf.get("/sso/oidc/login/callback/")
    SessionMiddleware(lambda _: None).process_request(request)  # pyright: ignore[reportArgumentType], # ty: ignore[invalid-argument-type]
    request.session.save()
    MessageMiddleware(lambda _: None).process_request(request)  # pyright: ignore[reportArgumentType], # ty: ignore[invalid-argument-type]
    request.user = AnonymousUser()
    return request


def _complete_social_login(request, sociallogin: SocialLogin):
    """Run the real login/signup flow inside allauth's request context."""
    with context.request_context(request):
        response = complete_social_login(request, sociallogin)
    # Every Codex path ends in a redirect; narrows the Optional for
    # the type checkers as a bonus.
    assert response is not None
    return response


class OIDCDisabledTests(TestCase):
    """Every OIDC path must 404 when the feature is off (the default)."""

    def test_init_endpoint_404(self) -> None:
        response = self.client.get("/api/v4/auth/oidc/login")
        assert response.status_code == _HTTP_NOT_FOUND

    def test_allauth_login_path_404(self) -> None:
        """Allauth's own view 404s: no SocialApp exists when APPS is empty."""
        response = self.client.get("/sso/oidc/login/")
        assert response.status_code == _HTTP_NOT_FOUND

    def test_allauth_callback_path_404(self) -> None:
        response = self.client.get("/sso/oidc/login/callback/")
        assert response.status_code == _HTTP_NOT_FOUND


class OIDCInitTests(TestCase):
    """The branded init endpoint redirects into allauth when enabled."""

    def test_init_redirects_to_allauth_login(self) -> None:
        _seed_oidc()
        response = self.client.get("/api/v4/auth/oidc/login")
        assert response.status_code == _HTTP_FOUND
        assert response["Location"] == "/sso/oidc/login/"


class OIDCProvisionTests(TestCase):
    """User provisioning and username mapping through the real signup flow."""

    @override
    def setUp(self) -> None:
        _seed_oidc()
        self.rf = RequestFactory()  # pyright: ignore[reportUninitializedInstanceVariable]

    def _complete(self, sociallogin: SocialLogin):
        return _complete_social_login(_request(self.rf), sociallogin)

    def test_creates_user_from_preferred_username(self) -> None:
        sociallogin = _sociallogin(
            id_token={"sub": _SUB},
            userinfo={"preferred_username": "aj", "email": "aj@example.com"},
        )
        response = self._complete(sociallogin)
        assert response.status_code == _HTTP_FOUND
        user = User.objects.get(username="aj")
        assert user.email == "aj@example.com"
        assert not user.has_usable_password()
        assert SocialAccount.objects.get(user=user).uid == _SUB

    def test_username_falls_back_to_email_then_sub(self) -> None:
        sociallogin = _sociallogin(
            id_token={"sub": _SUB}, userinfo={"email": "fallback@example.com"}
        )
        self._complete(sociallogin)
        assert User.objects.filter(username="fallback@example.com").exists()

        sociallogin = _sociallogin(id_token={"sub": "sub-bare"}, sub="sub-bare")
        self._complete(sociallogin)
        assert User.objects.filter(username="sub-bare").exists()

    def test_claims_merged_id_token_and_userinfo(self) -> None:
        """A claim present only in the ID token (Authentik groups) is seen."""
        sociallogin = _sociallogin(
            id_token={"sub": _SUB, "groups": ["readers"]},
            userinfo={"preferred_username": "aj"},
        )
        claims = merged_claims(sociallogin)
        assert claims["groups"] == ["readers"]
        assert claims["preferred_username"] == "aj"

    def test_create_users_off_redirects_to_error(self) -> None:
        _seed_oidc(create_users=False)
        sociallogin = _sociallogin(
            id_token={"sub": _SUB}, userinfo={"preferred_username": "nobody"}
        )
        response = self._complete(sociallogin)
        assert response.status_code == _HTTP_FOUND
        assert response["Location"] == f"{_SSO_ERROR}?error=signup_disabled"
        assert not User.objects.filter(username="nobody").exists()


class OIDCLinkingTests(TestCase):
    """Account-linking policy: username always, superusers included."""

    @override
    def setUp(self) -> None:
        _seed_oidc()
        self.rf = RequestFactory()  # pyright: ignore[reportUninitializedInstanceVariable]

    def _complete(self, sociallogin: SocialLogin):
        return _complete_social_login(_request(self.rf), sociallogin)

    def test_links_existing_user_by_username(self) -> None:
        local = User.objects.create_user("aj", "old@example.com")
        sociallogin = _sociallogin(
            id_token={"sub": _SUB}, userinfo={"preferred_username": "AJ"}
        )
        response = self._complete(sociallogin)
        assert response.status_code == _HTTP_FOUND
        account = SocialAccount.objects.get(uid=_SUB)
        assert account.user == local
        assert User.objects.count() == 1

    def test_links_superuser_by_username(self) -> None:
        """Chosen behavior, not an accident: superusers auto-link too."""
        admin = User.objects.create_superuser("admin", "", "admin")
        sociallogin = _sociallogin(
            id_token={"sub": _SUB}, userinfo={"preferred_username": "admin"}
        )
        self._complete(sociallogin)
        assert SocialAccount.objects.get(uid=_SUB).user == admin

    def test_different_sub_does_not_hijack_linked_user(self) -> None:
        """Same preferred_username, different sub: new user, no hijack."""
        local = User.objects.create_user("aj")
        SocialAccount.objects.create(user=local, provider="oidc", uid=_SUB)
        sociallogin = _sociallogin(
            id_token={"sub": "sub-other"},
            userinfo={"preferred_username": "aj"},
            sub="sub-other",
        )
        self._complete(sociallogin)
        other = SocialAccount.objects.get(uid="sub-other").user
        assert other != local
        # Collision resolved with a sub-hash suffix, keeping the identity.
        assert other.username.startswith("aj-")

    def test_email_conflict_redirects_when_link_by_email_off(self) -> None:
        User.objects.create_user("existing", "aj@example.com")
        sociallogin = _sociallogin(
            id_token={"sub": _SUB},
            userinfo={"preferred_username": "newname", "email": "aj@example.com"},
        )
        response = self._complete(sociallogin)
        assert response.status_code == _HTTP_FOUND
        assert response["Location"] == f"{_SSO_ERROR}?error=email_exists"
        assert not User.objects.filter(username="newname").exists()

    def test_links_by_email_when_enabled(self) -> None:
        local = User.objects.create_user("existing", "aj@example.com")
        _seed_oidc(link_by_email=True)
        sociallogin = _sociallogin(
            id_token={"sub": _SUB},
            userinfo={"preferred_username": "newname", "email": "AJ@example.com"},
        )
        response = self._complete(sociallogin)
        assert response.status_code == _HTTP_FOUND
        assert SocialAccount.objects.get(uid=_SUB).user == local


class OIDCGroupSyncTests(TestCase):
    """Group and admin mapping from the groups claim."""

    @override
    def setUp(self) -> None:
        _seed_oidc(sync_groups=True)
        self.rf = RequestFactory()  # pyright: ignore[reportUninitializedInstanceVariable]
        self.readers = Group.objects.create(name="readers")  # pyright: ignore[reportUninitializedInstanceVariable]
        self.user = User.objects.create_user("aj")  # pyright: ignore[reportUninitializedInstanceVariable]
        SocialAccount.objects.create(user=self.user, provider="oidc", uid=_SUB)

    def _login_with_groups(self, groups) -> None:
        sociallogin = _sociallogin(
            id_token={"sub": _SUB, "groups": groups},
            userinfo={"preferred_username": "aj"},
        )
        _complete_social_login(_request(self.rf), sociallogin)
        self.user.refresh_from_db()

    def test_sync_sets_existing_groups_only(self) -> None:
        self._login_with_groups(["readers", "not-a-codex-group"])
        assert list(self.user.groups.all()) == [self.readers]
        assert not Group.objects.filter(name="not-a-codex-group").exists()

    def test_sync_removes_dropped_groups(self) -> None:
        self.user.groups.add(self.readers)
        self._login_with_groups([])
        assert not self.user.groups.exists()

    def test_absent_groups_claim_is_noop(self) -> None:
        self.user.groups.add(self.readers)
        sociallogin = _sociallogin(
            id_token={"sub": _SUB}, userinfo={"preferred_username": "aj"}
        )
        _complete_social_login(_request(self.rf), sociallogin)
        self.user.refresh_from_db()
        assert list(self.user.groups.all()) == [self.readers]

    def test_admin_group_grants_and_revokes(self) -> None:
        _seed_oidc(sync_groups=True, admin_group="codex-admins")
        self._login_with_groups(["codex-admins"])
        assert self.user.is_staff
        assert self.user.is_superuser
        self._login_with_groups(["readers"])
        assert not self.user.is_staff
        assert not self.user.is_superuser


class OIDCSessionFlagTests(TestCase):
    """The /session payload advertises OIDC state to the SPA."""

    @override
    def setUp(self) -> None:
        """Seed the AdminFlag + Timestamp rows /session requires."""
        from codex.startup import init_admin_flags, init_timestamps

        init_admin_flags()
        init_timestamps()

    def test_sso_error_route_resolves_to_spa_index(self) -> None:
        """
        ``/auth/sso-error`` serves the SPA, not the catch-all redirect.

        The adapter's error redirects land here; without the explicit app
        urlconf entry the catch-all would 302 the error page to home.
        """
        match = resolve("/auth/sso-error")
        assert match.view_name == "app:sso-error"

    def test_disabled_flags_logged_out(self) -> None:
        data = self.client.get("/api/v4/session").json()["data"]
        flags = data["adminFlags"]
        assert flags["oidcEnabled"] is False
        assert "oidcProviderName" not in flags
        assert "oidcLoginUrl" not in flags
        assert "oidcLogoutUrl" not in flags

    def test_enabled_flags_are_public_and_prefixed(self) -> None:
        _seed_oidc(provider_name="Authentik")
        data = self.client.get("/api/v4/session").json()["data"]
        flags = data["adminFlags"]
        assert flags["oidcEnabled"] is True
        assert flags["oidcProviderName"] == "Authentik"
        assert flags["oidcLoginUrl"] == (
            f"{GRANIAN_URL_PATH_PREFIX}/api/v4/auth/oidc/login"
        )
        # Logged out: no logout URL even when rp logout is configured.
        assert "oidcLogoutUrl" not in flags


class OIDCLogoutURLTests(TestCase):
    """RP-initiated logout URL construction from the discovery document."""

    @override
    def setUp(self) -> None:
        cache.delete(DISCOVERY_CACHE_KEY)
        self.rf = RequestFactory()  # pyright: ignore[reportUninitializedInstanceVariable]

    def _logout_url(self, discovery: dict) -> str:
        _seed_oidc(rp_initiated_logout=True)
        request = self.rf.get("/api/v4/session")
        with patch("codex.oidc._discovery_document", return_value=discovery):
            return oidc_logout_url(request)

    def test_builds_end_session_url(self) -> None:
        url = self._logout_url(
            {"end_session_endpoint": "https://idp.example.com/end-session/"}
        )
        assert url.startswith("https://idp.example.com/end-session/?")
        assert "client_id=codex-test" in url
        assert "post_logout_redirect_uri=" in url

    def test_empty_when_provider_has_no_end_session(self) -> None:
        """Authelia's discovery document omits end_session_endpoint."""
        assert self._logout_url({}) == ""

    def test_empty_when_disabled(self) -> None:
        request = self.rf.get("/api/v4/session")
        assert oidc_logout_url(request) == ""


class OIDCUsernameLockTests(TestCase):
    """Linked accounts get a read-only username in profile serializers."""

    def _username_read_only(self, user) -> bool:
        request = RequestFactory().get("/api/v4/auth/profile")
        request.user = user
        serializer = ProfileUpdateSerializer(context={"request": request})
        return serializer.fields["username"].read_only

    def test_locked_when_oidc_linked(self) -> None:
        user = User.objects.create_user("aj")
        SocialAccount.objects.create(user=user, provider="oidc", uid=_SUB)
        assert self._username_read_only(user) is True

    def test_unlocked_for_local_user(self) -> None:
        user = User.objects.create_user("aj")
        assert self._username_read_only(user) is False


class OIDCSchemaTests(TestCase):
    """allauth's plain Django views must not leak into the API schema."""

    def test_allauth_views_absent_from_schema(self) -> None:
        admin = User.objects.create_superuser("admin", "", "admin")
        self.client.force_login(admin)
        response = self.client.get("/api/v4/schema")
        assert response.status_code == _HTTP_OK
        paths = response.data["paths"]  # pyright: ignore[reportAttributeAccessIssue], # ty: ignore[missing-attribute]
        sso_paths = [path for path in paths if "/sso/" in path]
        assert sso_paths == []
        # The DRF init endpoint is a documented part of the API.
        assert any(path.endswith("/auth/oidc/login") for path in paths)


class OIDCErrorTests(TestCase):
    """Authentication errors land on the SPA error page, never a template."""

    def _error_location(self, error) -> str:
        adapter = CodexSocialAccountAdapter()
        request = RequestFactory().get("/sso/oidc/login/callback/")
        try:
            adapter.on_authentication_error(request, provider=None, error=error)
        except ImmediateHttpResponse as exc:
            return exc.response["Location"]
        msg = "on_authentication_error did not raise"
        raise AssertionError(msg)

    def test_known_error_passes_through(self) -> None:
        assert self._error_location("access_denied") == (
            f"{_SSO_ERROR}?error=access_denied"
        )

    def test_unknown_error_collapses_to_server_error(self) -> None:
        """Never reflect arbitrary provider input into the redirect."""
        assert self._error_location("<script>") == (f"{_SSO_ERROR}?error=server_error")

    def test_no_error_defaults_to_server_error(self) -> None:
        assert self._error_location(None) == f"{_SSO_ERROR}?error=server_error"

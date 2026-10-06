"""
Native OIDC (SSO) login via django-allauth.

The allauth apps are always installed (see ``codex.settings``); everything
here is gated at runtime on the :class:`codex.models.admin.OIDCSettings`
DB singleton, edited in the Admin UI Auth tab. cachalot caches the row and
invalidates it on write, so enabling, disabling, or repointing the
identity provider takes effect on the next request without a restart.
The flow is:

1. ``GET /api/v4/auth/oidc/login`` (:class:`OIDCLoginRedirectView`, throttled,
   404 when disabled) redirects to allauth's provider login view.
2. allauth redirects to the identity provider's authorize endpoint
   (state + PKCE bound to the Django session). allauth discovers the
   provider app through :meth:`CodexSocialAccountAdapter.list_apps`,
   which builds an unsaved ``SocialApp`` from the DB singleton — when
   OIDC is off there is no app, so allauth's own
   ``SocialApp.DoesNotExist -> Http404`` keeps every path a clean 404.
3. The provider redirects back to ``/sso/oidc/login/callback/`` where
   allauth exchanges the code and builds a ``SocialLogin``.
4. :class:`CodexSocialAccountAdapter` links or provisions the Django user
   and allauth logs it in with a normal session cookie, landing on the SPA
   root where ``loadSession()`` picks up the session.

Every signup path resolves inside the adapter: failures and policy
rejections redirect to the SPA's ``/auth/sso-error`` route instead of ever
rendering an allauth template.
"""

from hashlib import sha256
from typing import TYPE_CHECKING, NoReturn, override
from urllib.parse import urlencode

import requests
from allauth.account.utils import user_username
from allauth.core.exceptions import ImmediateHttpResponse
from allauth.socialaccount.adapter import DefaultSocialAccountAdapter
from django.contrib.auth.models import Group, User
from django.core.cache import cache
from django.http import Http404, HttpResponseRedirect
from django.shortcuts import redirect
from django.urls import reverse
from loguru import logger
from rest_framework.views import APIView

from codex.failed_login_log import log_failed_login
from codex.settings import GRANIAN_URL_PATH_PREFIX
from codex.settings.db import get_oidc_settings, oidc_enabled
from codex.throttling import ScopedRateThrottle

if TYPE_CHECKING:
    from allauth.socialaccount.models import SocialApp, SocialLogin
    from django.http import HttpRequest

    from codex.models.admin import OIDCSettings

_SSO_ERROR_PATH = f"{GRANIAN_URL_PATH_PREFIX}/auth/sso-error"
_OIDC_PROVIDER_ID = "oidc"
_DEFAULT_USERNAME_CLAIM = "preferred_username"
# OAuth2 error codes passed through to the SPA error page; anything else
# collapses to server_error so the redirect never reflects attacker input.
_KNOWN_ERRORS = frozenset(
    {
        "access_denied",
        "email_exists",
        "server_error",
        "signup_disabled",
        "temporarily_unavailable",
    }
)


DISCOVERY_CACHE_KEY = "codex-oidc-discovery"
_DISCOVERY_CACHE_TTL = 60 * 60
_DISCOVERY_FAILURE_TTL = 60 * 5
_DISCOVERY_TIMEOUT = 5
_WELL_KNOWN = "/.well-known/openid-configuration"


def user_is_oidc_managed(user) -> bool:
    """Return whether the user's identity is owned by the identity provider."""
    return bool(
        user and user.pk and user.is_authenticated and user.socialaccount_set.exists()
    )


def discovery_url(server_url: str) -> str:
    """Return the well-known discovery URL for an issuer URL."""
    if "/.well-known/" in server_url:
        return server_url
    return server_url.rstrip("/") + _WELL_KNOWN


def fetch_discovery_document(server_url: str) -> dict:
    """
    Fetch the provider's OIDC discovery document, uncached.

    Raises ``requests.RequestException`` or ``ValueError`` on failure —
    used directly by the Admin UI's Test Connection endpoint.
    """
    response = requests.get(discovery_url(server_url), timeout=_DISCOVERY_TIMEOUT)
    response.raise_for_status()
    return response.json()


def _discovery_document(server_url: str) -> dict:
    """
    Fetch and cache the provider's OIDC discovery document.

    Failures are negative-cached briefly so an unreachable identity
    provider can't turn every session boot into a hanging request.
    """
    doc = cache.get(DISCOVERY_CACHE_KEY)
    if doc is not None:
        return doc
    try:
        doc = fetch_discovery_document(server_url)
    except (requests.RequestException, ValueError) as exc:
        logger.warning(f"OIDC discovery fetch failed: {type(exc).__name__}")
        cache.set(DISCOVERY_CACHE_KEY, {}, _DISCOVERY_FAILURE_TTL)
        return {}
    cache.set(DISCOVERY_CACHE_KEY, doc, _DISCOVERY_CACHE_TTL)
    return doc


def oidc_logout_url(request: "HttpRequest") -> str:
    """
    Build the RP-initiated logout URL, or "" when unavailable.

    Uses the spec's ``client_id`` + ``post_logout_redirect_uri``
    parameters — no ``id_token_hint`` because allauth does not retain the
    raw ID token JWT. Authentik accepts this; Authelia has no end_session
    endpoint, so its discovery document simply omits the key.
    """
    row = get_oidc_settings()
    if not (oidc_enabled(row) and row and row.rp_initiated_logout):
        return ""
    end_session = _discovery_document(row.server_url).get("end_session_endpoint")
    if not end_session:
        return ""
    post_logout = request.build_absolute_uri(GRANIAN_URL_PATH_PREFIX or "/")
    params = urlencode(
        {"client_id": row.client_id, "post_logout_redirect_uri": post_logout}
    )
    return f"{end_session}?{params}"


def _raise_sso_error(error: str) -> NoReturn:
    """Abort the login flow with a redirect to the SPA's SSO error page."""
    if error not in _KNOWN_ERRORS:
        error = "server_error"
    raise ImmediateHttpResponse(redirect(f"{_SSO_ERROR_PATH}?error={error}"))


def merged_claims(sociallogin: "SocialLogin") -> dict:
    """
    Merge ID-token and userinfo claims into one mapping; userinfo wins.

    allauth's openid_connect provider stores ``extra_data`` as
    ``{"id_token": {...}, "userinfo": {...}}`` but its ``_pick_data``
    *prefers* userinfo rather than merging, so a claim present only in the
    ID token (e.g. Authentik's ``groups``) would be invisible. Merging
    tolerates both Authentik (claims in the ID token) and Authelia
    (claims only in userinfo).
    """
    extra = sociallogin.account.extra_data or {}
    id_token = extra.get("id_token") or {}
    userinfo = extra.get("userinfo") or {}
    if id_token or userinfo:
        return id_token | userinfo
    # Pre-65.11 allauth stored a flat claims dict.
    return dict(extra)


def _map_username(claims: dict, row: "OIDCSettings | None") -> str:
    """Map claims to a Codex username: username_claim -> email -> sub."""
    claim = (row.username_claim if row else "") or _DEFAULT_USERNAME_CLAIM
    username = claims.get(claim) or claims.get("email") or claims.get("sub") or ""
    return str(username)


def _build_social_app(row: "OIDCSettings") -> "SocialApp":
    """
    Build allauth's unsaved SocialApp from the DB singleton.

    The same shape allauth itself builds from
    ``SOCIALACCOUNT_PROVIDERS[...]["APPS"]`` entries — per-app
    ``settings["scope"]`` wins over provider-level SCOPE in
    ``OAuth2Provider.get_scope``.
    """
    from allauth.socialaccount.models import SocialApp

    app_settings = {
        "server_url": row.server_url,
        "oauth_pkce_enabled": row.pkce,
        "fetch_userinfo": row.fetch_userinfo,
        "scope": row.scope.split(),
    }
    if row.token_auth_method:
        app_settings["token_auth_method"] = row.token_auth_method
    return SocialApp(
        provider="openid_connect",
        provider_id=_OIDC_PROVIDER_ID,
        name=row.provider_name or "SSO",
        client_id=row.client_id,
        secret=row.client_secret,
        settings=app_settings,
    )


class CodexSocialAccountAdapter(DefaultSocialAccountAdapter):
    """Link, provision, and sync Codex users from OIDC claims."""

    @override
    def list_apps(self, request, provider=None, client_id=None) -> list:
        """
        Blend in the OIDC app configured by the Admin UI singleton.

        Mirrors allauth's own filter semantics for settings-configured
        apps. When OIDC is disabled no app exists, so allauth's provider
        views 404 on their own.
        """
        apps = super().list_apps(request, provider=provider, client_id=client_id)
        row = get_oidc_settings()
        if not (oidc_enabled(row) and row):
            return apps
        app = _build_social_app(row)
        if client_id and app.client_id != client_id:
            return apps
        if provider and provider not in (app.provider, app.provider_id):
            return apps
        apps.append(app)
        return apps

    @override
    def is_open_for_signup(self, request, sociallogin) -> bool:
        """Gate auto-provisioning on the create_users config knob."""
        row = get_oidc_settings()
        return bool(row and row.create_users)

    @override
    def pre_social_login(self, request, sociallogin) -> None:
        """
        Resolve every login path before allauth's signup machinery runs.

        Linking policy (user decision, documented in the README): an OIDC
        login auto-links to an existing local user with the same username —
        including superusers — and by email only when ``link_by_email`` is
        on. Linking records the SocialAccount keyed on the stable ``sub``
        claim, so later logins match by sub even if the username changes.
        """
        row = get_oidc_settings()
        claims = merged_claims(sociallogin)
        if sociallogin.is_existing:
            # Known sub: sync and let allauth log the user in.
            self._sync_user(sociallogin.user, claims, row)
            return
        if user := self._find_linkable_user(claims, row):
            sociallogin.connect(request, user)
            self._sync_user(user, claims, row)
            return
        if not (row and row.create_users):
            log_failed_login(request, _map_username(claims, row))
            _raise_sso_error("signup_disabled")
        if self._email_conflict(claims):
            # Unlinked local user owns this email and link_by_email is
            # off. Without this check allauth would render its own signup
            # form into the SPA-less void.
            log_failed_login(request, _map_username(claims, row))
            _raise_sso_error("email_exists")

    @override
    def populate_user(self, request, sociallogin, data):
        """
        Apply the configured username claim chain to new users.

        If the mapped username is already taken (an already-linked account
        owns it, so pre_social_login won't link), suffix with a short hash
        of the sub. Without this, allauth blanks the colliding username and
        falls back to a generic "user" name.
        """
        user = super().populate_user(request, sociallogin, data)
        row = get_oidc_settings()
        if username := _map_username(merged_claims(sociallogin), row):
            if User.objects.filter(username__iexact=username).exists():
                sub_hash = sha256(str(sociallogin.account.uid).encode()).hexdigest()
                username = f"{username}-{sub_hash[:8]}"
            user_username(user, username)
        return user

    @override
    def save_user(self, request, sociallogin, form=None):
        """Provision a new user, then sync groups/admin from claims."""
        user = super().save_user(request, sociallogin, form)
        self._sync_user(user, merged_claims(sociallogin), get_oidc_settings())
        return user

    @override
    def on_authentication_error(
        self, request, provider, error=None, exception=None, extra_context=None
    ) -> None:
        """Log the failure and land on the SPA error page, never a template."""
        del provider, extra_context
        # Same record format as password failures so fail2ban regexes and
        # the dedicated-log privacy story apply unchanged. When the
        # failed-login log is disabled the record is dropped by the main
        # sinks' filter, so this degrades gracefully.
        log_failed_login(request)
        code = str(error) if error else "server_error"
        if exception:  # pragma: no cover - depends on provider behavior
            # str(exception) may embed tokens or secrets; log type only.
            log_failed_login(request, f"oidc-exception={type(exception).__name__}")
        _raise_sso_error(code)

    @staticmethod
    def _find_linkable_user(claims: dict, row: "OIDCSettings | None") -> User | None:
        """
        Find an existing unlinked local user to attach this login to.

        Skips users that already have an OIDC link (a different sub with
        the same preferred_username must not hijack their account).
        """
        if username := _map_username(claims, row):
            user = User.objects.filter(username__iexact=username).first()
            if user and not user.socialaccount_set.exists():  # pyright: ignore[reportAttributeAccessIssue], # ty: ignore[unresolved-attribute]
                return user
        if row and row.link_by_email and (email := claims.get("email")):
            user = User.objects.filter(email__iexact=str(email)).first()
            if user and not user.socialaccount_set.exists():  # pyright: ignore[reportAttributeAccessIssue], # ty: ignore[unresolved-attribute]
                return user
        return None

    @staticmethod
    def _email_conflict(claims: dict) -> bool:
        """Return whether creating this user collides with an existing email."""
        email = claims.get("email")
        return bool(email and User.objects.filter(email__iexact=str(email)).exists())

    @staticmethod
    def _sync_user(user, claims: dict, row: "OIDCSettings | None") -> None:
        """
        Sync Django groups and admin flags from the groups claim.

        Runs on every OIDC login so library ACLs track the identity
        provider. An absent or malformed groups claim is a no-op — Authelia
        omits it entirely unless the ``groups`` scope is requested. Only
        EXISTING Codex groups are matched; groups are never created because
        they gate library ACLs.
        """
        if not (user and row and (row.sync_groups or row.admin_group)):
            return
        group_names = claims.get(row.groups_claim or "groups")
        if not isinstance(group_names, list):
            return
        names = {str(name) for name in group_names}
        if row.sync_groups:
            user.groups.set(Group.objects.filter(name__in=names))
        if row.admin_group:
            # The identity provider is authoritative: grants AND revokes.
            CodexSocialAccountAdapter._sync_admin(
                user, is_admin=row.admin_group in names
            )

    @staticmethod
    def _sync_admin(user, *, is_admin: bool) -> None:
        """Grant or revoke staff+superuser to match the admin-group claim."""
        if user.is_staff != is_admin or user.is_superuser != is_admin:
            user.is_staff = user.is_superuser = is_admin
            user.save(update_fields=("is_staff", "is_superuser"))


class OIDCLoginRedirectView(APIView):
    """
    Branded, throttled entry point for OIDC login.

    A plain GET navigation (not XHR): the SPA sets
    ``window.location.href`` here and the chain of redirects ends back at
    the SPA root with a session cookie. 404s when OIDC is disabled, like
    RegisterView does when registration is off.
    """

    authentication_classes = ()
    throttle_classes = (ScopedRateThrottle,)
    throttle_scope = "oidc_login"

    def get(self, request: "HttpRequest") -> HttpResponseRedirect:
        """Redirect to allauth's provider login view."""
        del request
        if not oidc_enabled():
            raise Http404
        url = reverse("openid_connect_login", kwargs={"provider_id": _OIDC_PROVIDER_ID})
        return HttpResponseRedirect(url)

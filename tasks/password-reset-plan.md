# Codex Password Reset via Email — Implementation Checklist

Self-service password reset using django-rest-registration's
reset-password verification workflow. Feature is gated on a configured
SMTP server: with no `[email]` block in `codex.toml`, all reset and
email-verification surfaces stay hidden and endpoints respond 404.

## User Flow

1. User clicks "Forgot password?" on login dialog (only visible when
   `adminFlags.emailEnabled`).
2. Dialog asks for username or email → POST
   `/api/v3/auth/send-reset-password-link/`.
3. Backend signs a token, renders email template with a link back to a
   frontend route, sends via SMTP.
4. User clicks link → lands on
   `/auth/reset-password/?user_id=…&timestamp=…&signature=…` in the SPA.
5. Frontend form takes new password → POST
   `/api/v3/auth/reset-password/` with the URL params + password.
6. Success → redirect to login.

## Decisions (confirmed)

- **Email field**: unhidden for users; self-service editing via new
  Profile dialog (Phase 5).
- **Registration verification**: gated by a new admin flag
  (`REGISTER_VERIFICATION`), runtime-toggleable; only takes effect when
  email is also configured.
- **`from_address`**: falls back to `email.user` when blank. Admin docs
  must call out that some providers (Gmail, SES) require an explicit
  verified `from_address`.

## Phase 1: Email/SMTP Config

- [ ] Add `# Codex Config: Email` block in
      `codex/settings/__init__.py` after the existing Auth block:
  - `EMAIL_HOST` ← `email.host` (default `""`)
  - `EMAIL_PORT` ← `email.port` (default `587`)
  - `EMAIL_HOST_USER` ← `email.user` (default `""`)
  - `EMAIL_HOST_PASSWORD` ← `email.password` (default `""`)
  - `EMAIL_USE_TLS` ← `email.use_tls` (default `True`)
  - `EMAIL_USE_SSL` ← `email.use_ssl` (default `False`)
  - `EMAIL_TIMEOUT` ← `email.timeout` (default `10`)
  - `DEFAULT_FROM_EMAIL` ← `email.from_address`, fallback to
    `EMAIL_HOST_USER` if blank
  - `SERVER_EMAIL = DEFAULT_FROM_EMAIL`
  - `EMAIL_ENABLED = bool(EMAIL_HOST and DEFAULT_FROM_EMAIL)`
  - `EMAIL_BACKEND = "django.core.mail.backends.smtp.EmailBackend" if
    EMAIL_ENABLED else "django.core.mail.backends.dummy.EmailBackend"`
- [ ] Document `[email]` section in `codex/settings/codex.toml.default`
      with one Gmail-app-password example and an SES example, both
      commented out. Call out the `from_address` fallback and which
      providers require it set explicitly.
- [ ] Add `THROTTLE_RESET_PASSWORD = get_int(CODEX_CONFIG,
      "throttle.reset_password", default=5)` (per hour) and document in
      `codex.toml.default`.
- [ ] Verify: `codex` starts cleanly with no `[email]` section
      (`EMAIL_ENABLED=False`); with a `[email]` block pointing at
      mailcatcher/MailHog, `from django.core.mail import send_mail;
      send_mail(...)` lands a message.

## Phase 2: REST Registration Wiring

- [ ] Update `REST_REGISTRATION` dict at
      `codex/settings/__init__.py:784`:
  - `RESET_PASSWORD_VERIFICATION_ENABLED = EMAIL_ENABLED`
  - `RESET_PASSWORD_VERIFICATION_URL = "/auth/reset-password/"`
  - `RESET_PASSWORD_VERIFICATION_AUTO_LOGIN = False`
  - `RESET_PASSWORD_VERIFICATION_ONE_TIME_USE = True`
  - `VERIFICATION_FROM_EMAIL = DEFAULT_FROM_EMAIL`
  - `VERIFICATION_TEMPLATE_CONTEXT_BUILDER =
    "codex.auth.email.build_reset_context"` (handles
    `URL_PATH_PREFIX` for reverse-proxy installs)
  - Remove `"email"` from `USER_HIDDEN_FIELDS`
  - `USER_EMAIL_FIELD = "email"`
  - `USER_LOGIN_FIELDS = ("username", "email")` (accept either at
    login + send-reset-link)
- [ ] Create `codex/auth/__init__.py` and
      `codex/auth/email.py::build_reset_context(user, request)` that
      builds an absolute URL respecting `GRANIAN_URL_PATH_PREFIX`.
- [ ] Ship templates at
      `codex/templates/rest_registration/reset_password/`:
  - `subject.txt` (single line, no trailing newline)
  - `body.txt` (plain text, link + expiry note + "if this wasn't you,
    ignore")
  - `body.html` (optional, minimal inline-styled mirror of the txt)
- [ ] Add a DRF throttle class `ResetPasswordThrottle` (scoped,
      `THROTTLE_RESET_PASSWORD/hour`). Apply via a custom view wrapper
      around rest-registration's `send-reset-password-link/` and
      `reset-password/` URLs (drop them from
      `rest_registration.api.urls` include and re-register the
      throttled subclasses in `codex/urls/api/auth.py`).
- [ ] Verify: with `EMAIL_BACKEND="locmem"`, POST to
      `/api/v3/auth/send-reset-password-link/` lands a message in
      `django.core.mail.outbox`; link contains correct host + prefix +
      three signed params.

## Phase 3: Admin Flag — Register Verification

- [ ] Add `REGISTER_VERIFICATION = "RV"` to
      `codex/choices/admin.py::AdminFlagChoices` and to
      `ADMIN_FLAG_CHOICES` ("Verify New User Email") and to
      `_ADMIN_FLAG_KEYS` in `codex/views/public.py:14`.
- [ ] Migration: seed `AdminFlag(key="RV", on=False)`.
- [ ] Set `REST_REGISTRATION["REGISTER_VERIFICATION_ENABLED"] =
      EMAIL_ENABLED` (statically — possibility gate).
- [ ] Wrap rest-registration's register view with a custom view that
      checks the `RV` flag at request time:
  - flag OFF → call super, then `user.is_active = True; user.save()`
    if rest-registration deactivated it
  - flag ON → call super as-is (verification email sent, user inactive
    until they click the link)
- [ ] Ship templates at
      `codex/templates/rest_registration/register/` (`subject.txt`,
      `body.txt`, optional `body.html`).
- [ ] Verify: `RV=off` + register → user `is_active=True`, no email
      sent. `RV=on` + email configured → user `is_active=False`, one
      message in outbox; clicking link activates.

## Phase 4: Capability Flags for Frontend

- [ ] Extend `codex/views/public.py::AdminFlagsView.get_object()` to
      merge two settings-derived booleans into the response:
  - `email_enabled` from `settings.EMAIL_ENABLED`
  - `remote_user_enabled` from `settings.AUTH_REMOTE_USER` (Phase 5
    uses this to disable username editing when an upstream IdP owns
    the identity)
- [ ] Update `codex/serializers/auth.py::AuthAdminFlagsSerializer`
      with `email_enabled` and `remote_user_enabled` (both
      `BooleanField(read_only=True)`).
- [ ] Verify: GET `/api/v3/auth/flags/` returns both flags reflecting
      current config.

## Phase 5: Profile Dialog (Self-Service Username + Email + Password)

- [ ] Rename `frontend/src/components/auth/change-password-dialog.vue`
      to `profile-dialog.vue`. Sections:
  - Username field (text input, validated):
    - Disabled with helper "Managed by upstream authentication" when
      `adminFlags.remoteUserEnabled` is true
    - Otherwise editable, with persistent helper text "Changing your
      username will require updating any OPDS or API clients
      configured with the old name."
    - Same validation rules rest-registration uses (Django
      `User.username` field — let the API surface uniqueness errors
      rather than duplicating client-side)
  - Email field (text input, validated, optional)
  - "Change password" expansion panel (current / new / confirm)
- [ ] Single Save button: PATCH `/api/v3/auth/profile/` for username
      and/or email, POST `/api/v3/auth/change-password/` only if
      password fields filled. Run sequentially; surface either error.
      Send only changed fields in the PATCH.
- [ ] Add `updateProfile(profile)` in
      `frontend/src/api/v3/auth.js` (PATCH `/auth/profile/`).
- [ ] Update `frontend/src/stores/auth.js` with `updateProfile` action
      and refresh `user` state on success. After a successful username
      change, ensure subsequent API calls (especially the throttled
      reset endpoints, which key off the user) continue to work — the
      session cookie is FK-based so no re-login should be required;
      verify in testing.
- [ ] Update `frontend/src/components/auth/auth-menu.vue`: replace the
      "Change Password" item with "Profile" (use `mdi-account-cog` or
      `mdi-account-edit`).
- [ ] Backend: when `settings.AUTH_REMOTE_USER` is true, the profile
      PATCH must reject changes to `username` (return 400 with a clear
      "managed by upstream authentication" message). Belt-and-braces
      against a client that bypasses the disabled UI.
- [ ] Empty-email handling: if `RV=on` and email is being changed,
      surface a hint that the new address will need re-verification (no
      enforcement yet — future enhancement).
- [ ] Verify: change email, change username, change password — each
      alone and all-at-once; both succeed and persist. With
      `AUTH_REMOTE_USER=True`, username field is disabled in UI AND
      backend rejects a forged PATCH. After username rename, bookmarks
      and API token still work without re-login.

## Phase 6: Frontend Reset UI

- [ ] Add API calls in `frontend/src/api/v3/auth.js`:
  - `sendResetPasswordLink({ login })` → POST
    `/auth/send-reset-password-link/`
  - `resetPassword(payload)` → POST `/auth/reset-password/`
- [ ] Add `sendResetPasswordLink` and `resetPassword` actions to
      `frontend/src/stores/auth.js`.
- [ ] In `frontend/src/components/auth/login-dialog.vue`, add a small
      "Forgot password?" text button under the password field, gated
      by `v-if="adminFlags.emailEnabled"`. Click opens a sibling
      dialog.
- [ ] Create
      `frontend/src/components/auth/reset-password-request-dialog.vue`:
      single `login` field, submit, then show "If that account has an
      email on file, a reset link has been sent." regardless of API
      result (no enumeration).
- [ ] Create
      `frontend/src/components/auth/reset-password-confirm.vue`
      mounted at a new route. Reads `user_id`, `timestamp`,
      `signature` from `$route.query`; shows new + confirm password
      fields; POSTs all four on submit; redirects to `/` and opens
      login on success.
- [ ] Add route to `frontend/src/plugins/router.js`:
      `{ name: "reset-password", path: "/auth/reset-password",
      component: () => import("@/components/auth/reset-password-confirm.vue") }`.
- [ ] Verify (manual, with MailHog): forgot-password flow end-to-end
      through SPA reload at the email link, lands on confirm form,
      submission updates password, subsequent login with new password
      works.

## Phase 7: Admin User Tab — Backfill Emails

- [ ] Add "Email" column to
      `frontend/src/components/admin/tabs/user-tab.vue` user list +
      inline-editable.
- [ ] Confirm the admin user serializer already exposes `email`; if
      not, unhide it on the admin-side serializer too.
- [ ] Verify: admin can set email on an existing user; that user can
      then complete a reset flow.

## Phase 8: Docs

- [ ] `codex/settings/codex.toml.default` — the `[email]` block is the
      primary user-facing reference. Include:
  - Gmail app-password example (with note: requires `from_address` =
    same as `user`)
  - Generic SMTP example (mailgun/sendgrid)
  - SES example (note: requires `from_address` = verified identity)
  - Note on file permissions for `codex.toml` (credentials in plain
    text)
- [ ] README — one paragraph under "Configuration": optional feature,
      link to codex.toml.default.
- [ ] Release/upgrade note: existing users have no email on file;
      either user sets via Profile dialog or admin backfills via User
      tab.

## Phase 9: Tests

Backend (`codex/tests/`):

- [ ] `EMAIL_ENABLED=False` → `/auth/send-reset-password-link/` and
      `/auth/reset-password/` return 404; `/auth/flags/` returns
      `email_enabled: false`.
- [ ] `EMAIL_ENABLED=True` with `EMAIL_BACKEND="locmem"` → valid
      `send-reset-password-link/` produces exactly one mail in
      `django.core.mail.outbox`; link points at
      `RESET_PASSWORD_VERIFICATION_URL` with three signed params and
      respects `GRANIAN_URL_PATH_PREFIX`.
- [ ] Reset confirm: valid signature + new password → password actually
      changes; invalid signature → 400; reused token → 400.
- [ ] Throttle: `THROTTLE_RESET_PASSWORD+1` requests in window → 429.
- [ ] Login enumeration safety: nonexistent username / email returns
      same 2xx as valid one.
- [ ] `RV=off` register → `is_active=True`, no outbox; `RV=on` +
      `EMAIL_ENABLED` → `is_active=False`, one outbox; verify endpoint
      activates.
- [ ] Profile PATCH: user updates own email → 200, DB updated.
- [ ] Profile PATCH: user updates own username → 200, DB updated;
      session still valid (no re-login); bookmarks/API token still
      resolve to the same user.
- [ ] Profile PATCH with `AUTH_REMOTE_USER=True` attempting username
      change → 400.
- [ ] Profile PATCH attempting to take an already-taken username →
      400 (rely on Django uniqueness; just confirm the error surfaces
      cleanly).

Frontend (`frontend/src/tests/`):

- [ ] `adminFlags.emailEnabled=false` hides the "Forgot password?"
      link.
- [ ] Reset request dialog submission calls the right API path with
      `{ login }`.
- [ ] Confirm route reads query params and posts them on submit.
- [ ] Profile dialog: username-only save, email-only save,
      password-only save, all-three save.
- [ ] Profile dialog: `adminFlags.remoteUserEnabled=true` renders the
      username field disabled with the upstream-auth helper text.

## Phase 10: Polish

- [ ] `make build-choices` (regenerates `frontend/src/choices/` with
      the new `REGISTER_VERIFICATION` admin flag).
- [ ] `make fix` + `make lint` + `make ty` + `make test` (Python +
      frontend).
- [ ] `make build-frontend` clean.
- [ ] Manual run-through with MailHog: full forgot-password loop, full
      register-verification loop (with `RV=on`).

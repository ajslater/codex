<template>
  <div id="auth" class="adminReadingColumn">
    <!--
      Account & Access policy flags moved here from the Users tab: they
      govern how people get in (registration, verification, anonymous
      browsing), which is this tab's subject.
    -->
    <AdminSection title="Account & Access">
      <FlagCard
        v-for="key in ACCESS_FLAG_KEYS"
        :key="`f${key}`"
        :item-key="key"
      />
    </AdminSection>
    <!--
      One parent section for the whole OIDC block: the prose, the config
      sub-sections, and the test probe. The `sub` sections render small
      overline titles with an indented left rule so their subordination
      to this header is visible.

      Most admins never configure OIDC, so the body hides behind a
      disclosure that starts collapsed unless OIDC is already enabled.
    -->
    <AdminSection title="OIDC Single Sign-On" :hint="collapsedHint">
      <template #actions>
        <AdminExpandToggle v-model="oidcExpanded">
          {{ oidcExpanded ? "Hide" : "Configure" }}
        </AdminExpandToggle>
      </template>
      <div v-if="oidcExpanded && !settings">
        <v-progress-circular indeterminate />
      </div>
      <v-form v-else-if="oidcExpanded" ref="form" @submit.prevent="saveDraft">
        <div class="adminProse">
          <p>
            Codex can log users in through an OIDC identity provider like
            Authentik or Authelia. When enabled, a
            <em>Login with {{ draft.providerName || "SSO" }}</em> button appears
            on the login dialog and the unauthorized screen. Local password
            login keeps working alongside it, so enabling or disabling OIDC
            never locks anyone out. Changes take effect immediately — no
            restart.
          </p>
          <p>
            Forward-auth gateways like tinyauth are not OIDC identity providers
            — they sign users in at the reverse proxy instead. For tinyauth (and
            Authelia or Authentik in proxy mode) use Remote-User header
            authentication, enabled with
            <code>CODEX_AUTH_REMOTE_USER=1</code> and documented in the README.
            Both methods can be on at once.
          </p>
          <p>
            Register this redirect URI with the identity provider:
            <code>{{ redirectUri }}</code>
          </p>
          <p>
            ⚠️ OIDC logins auto-link to existing local users by username —
            including admin accounts. Only point Codex at an identity provider
            whose username namespace you control, and change the default admin
            password.
          </p>
        </div>

        <AdminSection sub title="Identity Provider">
          <div class="adminCard">
            <!-- Always allow unchecking so a cleared server URL can never
               strand the switch in a checked, un-uncheckable state. -->
            <v-checkbox
              v-model="draft.enabled"
              label="Enable OIDC Login"
              :disabled="!draft.enabled && !canEnable"
              :hint="enableHint"
              persistent-hint
              density="compact"
              hide-details="auto"
            />
          </div>
          <div class="adminCard">
            <v-text-field
              v-model="draft.providerName"
              label="Provider Name"
              hint="The login button label."
              persistent-hint
              hide-details="auto"
              density="compact"
            />
          </div>
          <div class="adminCard">
            <v-text-field
              v-model="draft.serverUrl"
              label="Server URL"
              placeholder="https://auth.example.com/application/o/codex/"
              hint="Issuer URL. Discovery is fetched from
              <server-url>/.well-known/openid-configuration."
              persistent-hint
              :rules="urlRules"
              hide-details="auto"
              density="compact"
            />
          </div>
          <div class="adminCard">
            <v-text-field
              v-model="draft.clientId"
              label="Client ID"
              hint="Issued by the identity provider when you register Codex
                as a client application there."
              persistent-hint
              hide-details="auto"
              density="compact"
              autocomplete="off"
            />
          </div>
          <div class="adminCard">
            <!-- Hidden username proxy so password managers can pair the
               secret field, mirroring the email tab's a11y note. -->
            <input
              type="text"
              autocomplete="username"
              :value="draft.clientId || 'codex-oidc'"
              readonly
              tabindex="-1"
              aria-hidden="true"
              class="clientIdProxy"
            />
            <v-text-field
              v-model="clientSecretDraft"
              label="Client Secret"
              type="password"
              autocomplete="new-password"
              hide-details="auto"
              density="compact"
              :placeholder="
                settings.clientSecretSet ? 'New Client Secret' : 'Client Secret'
              "
              :hint="clientSecretHint"
              persistent-hint
            />
            <div v-if="settings.clientSecretSet" class="adminInlineActions">
              <ConfirmDialog
                button-text="Clear Credential"
                title-text="Clear OIDC Client Secret"
                text="Clear the saved OIDC client secret?"
                confirm-text="Clear"
                variant="text"
                size="small"
                :block="false"
                @confirm="clearClientSecret"
              />
            </div>
          </div>
          <div class="adminCard">
            <v-text-field
              v-model="draft.scope"
              label="Scope"
              hint="Space separated. Authelia group sync needs
              'openid profile email groups'."
              persistent-hint
              hide-details="auto"
              density="compact"
            />
          </div>
          <div class="adminCard">
            <v-checkbox
              v-model="draft.pkce"
              label="PKCE (S256)"
              hint="Proof Key for Code Exchange — proves to the identity
                provider that the login that finishes is the one Codex
                started, so an intercepted login code can't be redeemed by
                anyone else. Authentik and Authelia both support it;
                leave on."
              persistent-hint
              density="compact"
              hide-details="auto"
            />
          </div>
          <div class="adminCard">
            <v-checkbox
              v-model="draft.fetchUserinfo"
              label="Fetch Userinfo"
              hint="Required for Authelia, which serves username, email, and
              groups claims only from the userinfo endpoint."
              persistent-hint
              density="compact"
              hide-details="auto"
            />
          </div>
        </AdminSection>

        <AdminSection sub title="User Mapping">
          <div class="adminCard">
            <v-text-field
              v-model="draft.usernameClaim"
              label="Username Claim"
              hint="A claim is a field in the identity the provider sends.
                This one becomes the Codex username; falls back to email,
                then to the opaque account ID (sub)."
              persistent-hint
              hide-details="auto"
              density="compact"
            />
          </div>
          <div class="adminCard">
            <v-checkbox
              v-model="draft.createUsers"
              label="Create Users on First Login"
              density="compact"
              hide-details="auto"
            />
          </div>
          <div class="adminCard">
            <v-checkbox
              v-model="draft.linkByEmail"
              label="Link by Email"
              hint="Also link to existing local users by email address. Only
              enable if the identity provider verifies emails."
              persistent-hint
              density="compact"
              hide-details="auto"
            />
          </div>
          <div class="adminCard">
            <v-checkbox
              v-model="draft.syncGroups"
              label="Sync Groups"
              hint="Replace the user's Codex groups from the identity provider's
              groups claim on every login. Matches existing Codex groups only."
              persistent-hint
              density="compact"
              hide-details="auto"
            />
          </div>
          <div class="adminCard">
            <v-text-field
              v-model="draft.groupsClaim"
              label="Groups Claim"
              hint="The claim (identity field) that carries the user's group
                list. 'groups' for both Authentik and Authelia."
              persistent-hint
              hide-details="auto"
              density="compact"
            />
          </div>
          <div class="adminCard">
            <v-text-field
              v-model="draft.adminGroup"
              label="Admin Group"
              hint="Members of this identity-provider group become Codex admins;
              removal revokes. Blank disables admin mapping."
              persistent-hint
              hide-details="auto"
              density="compact"
            />
          </div>
        </AdminSection>

        <AdminSection sub title="Logout">
          <div class="adminCard">
            <v-checkbox
              v-model="draft.rpInitiatedLogout"
              label="Also Log Out of the Identity Provider"
              hint="OIDC RP-initiated logout. Supported by Authentik; not
              implemented by Authelia."
              persistent-hint
              density="compact"
              hide-details="auto"
            />
          </div>
        </AdminSection>

        <AdminActionBar
          save-text="Save Settings"
          :saving="saving"
          :save-disabled="!hasChanges"
          :revert-disabled="!hasChanges || saving"
          @revert="resetDraft"
        />
      </v-form>

      <div v-if="oidcExpanded && settings" class="adminTestForm">
        <AdminSection sub title="Test Connection">
          <div class="adminCard">
            <div class="adminFieldColumn">
              <p class="testHint">
                Fetches the discovery document for the server URL above (unsaved
                edits included) and reports the endpoints the provider
                advertises.
              </p>
              <div class="adminInlineActions">
                <v-btn
                  variant="tonal"
                  size="small"
                  :loading="testing"
                  :disabled="!draft.serverUrl"
                  @click="runTest"
                >
                  Test Connection
                </v-btn>
              </div>
              <div
                v-if="testResult"
                class="testResult"
                :class="{ ok: testResult.ok, error: !testResult.ok }"
              >
                <template v-if="testResult.ok">
                  Issuer: {{ testResult.issuer }} — authorization ✓, token ✓,
                  userinfo {{ testResult.userinfoEndpoint ? "✓" : "✗" }},
                  end-session
                  {{ testResult.endSessionEndpoint ? "✓" : "✗ (no RP logout)" }}
                </template>
                <template v-else>
                  {{ testResult.error || "Discovery fetch failed." }}
                </template>
              </div>
            </div>
          </div>
        </AdminSection>
      </div>
    </AdminSection>
  </div>
</template>

<script>
import { dequal } from "dequal";
import { mapActions, mapState } from "pinia";

import LIMITS from "@/choices/limits.json";
import { APP_BASE } from "@/api/v4/base";
import AdminActionBar from "@/components/admin/tabs/action-bar.vue";
import AdminSection from "@/components/admin/tabs/admin-section.vue";
import AdminExpandToggle from "@/components/admin/tabs/expand-toggle.vue";
import FlagCard from "@/components/admin/tabs/flag-card.vue";
import ConfirmDialog from "@/components/confirm-dialog.vue";
import { useAdminStore } from "@/stores/admin";

const EDITABLE_FIELDS = Object.freeze([
  "enabled",
  "providerName",
  "serverUrl",
  "clientId",
  "scope",
  "pkce",
  "tokenAuthMethod",
  "fetchUserinfo",
  "usernameClaim",
  "createUsers",
  "linkByEmail",
  "syncGroups",
  "groupsClaim",
  "adminGroup",
  "rpInitiatedLogout",
]);
const URL_REGEX = /^https?:\/\/\S+$/;
const URL_RULES = Object.freeze([
  (v) => !v || URL_REGEX.test(v) || "Enter a valid https URL",
  ["$maxLength", LIMITS.oidcUrlMaxLength],
]);
// Registration, Verify New User Email, Non-Users (anonymous browsing).
const ACCESS_FLAG_KEYS = Object.freeze(["RG", "RV", "NU"]);

export function canEnableOidc(draft) {
  // Mirrors the serializer gate: enabling requires a provider name (the
  // button label), a valid server URL, and a client ID.
  return Boolean(
    draft?.providerName &&
    draft?.clientId &&
    draft?.serverUrl &&
    URL_REGEX.test(draft.serverUrl),
  );
}

function pickFields(source) {
  const out = {};
  for (const key of EDITABLE_FIELDS) {
    out[key] = source?.[key] ?? "";
  }
  return out;
}

export default {
  name: "AdminAuthTab",
  components: {
    AdminActionBar,
    AdminExpandToggle,
    AdminSection,
    ConfirmDialog,
    FlagCard,
  },
  data() {
    return {
      ACCESS_FLAG_KEYS,
      draft: pickFields(undefined),
      clientSecretDraft: "",
      testing: false,
      testResult: undefined,
      saving: false,
      oidcExpanded: false,
      oidcExpandedInitialized: false,
      urlRules: URL_RULES,
    };
  },
  computed: {
    ...mapState(useAdminStore, {
      settings: (state) => state.oidcSettings,
    }),
    hasChanges() {
      if (this.clientSecretDraft) return true;
      return !dequal(this.draft, pickFields(this.settings));
    },
    canEnable() {
      return canEnableOidc(this.draft);
    },
    enableHint() {
      return this.canEnable || this.draft.enabled
        ? "Shows the SSO login button. Local password login stays available."
        : "Enter a provider name, valid server URL, and client ID below first.";
    },
    collapsedHint() {
      if (this.oidcExpanded) {
        return "";
      }
      return this.settings?.enabled
        ? `Enabled — logging in with ${this.settings.providerName || "SSO"}.`
        : "Not enabled. Log users in through an identity provider like Authentik or Authelia.";
    },
    clientSecretHint() {
      if (this.clientSecretDraft) {
        return "Will be saved with the rest of the OIDC settings.";
      }
      return this.settings.clientSecretSet
        ? "Credential set (encrypted at rest)"
        : "Not configured. Leave blank for public clients.";
    },
    redirectUri() {
      // APP_BASE always ends with a slash ("/" or "/codex/").
      return `${globalThis.location.origin}${APP_BASE}sso/oidc/login/callback/`;
    },
  },
  watch: {
    settings: {
      immediate: true,
      handler(value) {
        this.draft = pickFields(value);
        // Start expanded only for deployments already using OIDC; after
        // that the disclosure is the admin's to drive (saving a disable
        // doesn't slam the panel shut under them).
        if (value && !this.oidcExpandedInitialized) {
          this.oidcExpanded = Boolean(value.enabled);
          this.oidcExpandedInitialized = true;
        }
      },
    },
  },
  mounted() {
    // The Account & Access FlagCards read the Flag table.
    this.loadTables(["Flag"]);
    this.loadOidcSettings();
  },
  methods: {
    ...mapActions(useAdminStore, [
      "loadTables",
      "loadOidcSettings",
      "updateOidcSettings",
      "testOidcConnection",
    ]),
    resetDraft() {
      this.draft = pickFields(this.settings);
    },
    async saveDraft() {
      const form = this.$refs.form;
      if (form) {
        const { valid } = await form.validate();
        if (!valid) return;
      }
      const payload = { ...this.draft };
      if (this.clientSecretDraft) {
        payload.clientSecret = this.clientSecretDraft;
      }
      this.saving = true;
      try {
        await this.updateOidcSettings(payload);
        this.clientSecretDraft = "";
      } finally {
        this.saving = false;
      }
    },
    clearClientSecret() {
      this.updateOidcSettings({ clientSecret: "" });
    },
    async runTest() {
      this.testing = true;
      this.testResult = undefined;
      try {
        this.testResult = await this.testOidcConnection({
          serverUrl: this.draft.serverUrl,
        });
      } finally {
        this.testing = false;
      }
    },
  },
};
</script>

<style scoped lang="scss">
@use "@/components/admin/tabs/admin-section.scss";
@use "@/components/admin/tabs/design.scss" as d;

.adminTestForm {
  margin-top: d.$space-8;
}

.testHint {
  font-size: 0.9em;
  color: rgba(var(--v-theme-on-surface), 0.75);
}

.testResult {
  font-size: 0.9em;
  padding-top: 4px;
}

.testResult.ok {
  color: rgb(var(--v-theme-success));
}

.testResult.error {
  color: rgb(var(--v-theme-error));
}

.clientIdProxy {
  position: absolute;
  width: 1px;
  height: 1px;
  padding: 0;
  margin: -1px;
  border: 0;
  overflow: hidden;
  clip: rect(0, 0, 0, 0);
}
</style>

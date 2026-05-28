<template>
  <div id="email" class="adminContainer">
    <div v-if="!settings" class="adminGroup">
      <v-progress-circular indeterminate />
    </div>
    <v-form v-else ref="form" @submit.prevent="saveDraft">
      <div class="adminIntro">
        <p>
          Codex sends email only for user self-service flows the admin would
          otherwise have to handle by hand:
        </p>
        <ul>
          <li>
            <strong>Password reset.</strong> Users who forget their password
            request a one-time reset link from the login screen.
          </li>
          <li>
            <strong>New-user verification.</strong> Optional — when
            <em>Verify New User Email</em> is on under the Flags tab,
            self-registered accounts stay inactive until they click the
            verification link.
          </li>
        </ul>
        <p>
          Without an SMTP host, both flows are disabled and the related
          endpoints return 404. Codex does not send notifications, newsletters,
          or any other outbound mail.
        </p>
      </div>
      <div class="adminGroup">
        <div class="adminGroupHeader">
          <h3>SMTP Server</h3>
        </div>
        <div class="adminCard">
          <v-text-field
            v-model="draft.host"
            label="Host"
            placeholder="smtp.example.com"
            :rules="hostRules"
            hide-details="auto"
            density="compact"
          />
        </div>
        <div class="adminCard">
          <v-text-field
            v-model.number="draft.port"
            type="number"
            label="Port"
            min="1"
            max="65535"
            :rules="portRules"
            hide-details="auto"
            density="compact"
          />
        </div>
        <div class="adminCard">
          <v-checkbox
            v-model="draft.useTls"
            label="STARTTLS"
            density="compact"
            hide-details="auto"
          />
        </div>
        <div class="adminCard">
          <v-checkbox
            v-model="draft.useSsl"
            label="SSL on connect"
            density="compact"
            hide-details="auto"
          />
        </div>
        <div class="adminCard">
          <v-text-field
            v-model.number="draft.timeout"
            type="number"
            label="Timeout (seconds)"
            min="1"
            max="600"
            :rules="timeoutRules"
            hide-details="auto"
            density="compact"
          />
        </div>
      </div>

      <div class="adminGroup">
        <div class="adminGroupHeader">
          <h3>Authentication</h3>
        </div>
        <div class="adminCard">
          <v-text-field
            v-model="draft.user"
            label="Username"
            hide-details="auto"
            density="compact"
            autocomplete="off"
          />
        </div>
        <div class="adminCard">
          <!--
            A11y warning: "Password forms should have (optionally
            hidden) username fields for accessibility." Mirror the
            SMTP username here as a non-displayed, non-editable input
            so the browser / password manager can pair it with the
            password without the user seeing two SMTP username
            fields. The enclosing ``<v-form>`` already provides the
            ``<form>`` element this needs to count as a real
            password form.
          -->
          <input
            type="text"
            autocomplete="username"
            :value="draft.user || 'codex-smtp'"
            readonly
            tabindex="-1"
            aria-hidden="true"
            class="smtpUsernameProxy"
          />
          <v-text-field
            v-model="passwordDraft"
            label="Password or Token"
            type="password"
            autocomplete="new-password"
            hide-details="auto"
            density="compact"
            :placeholder="
              settings.passwordSet
                ? 'New Password or Token'
                : 'Password or Token'
            "
            :hint="passwordHint"
            persistent-hint
          />
          <div v-if="settings.passwordSet" class="credentialActions">
            <v-btn variant="text" size="small" @click="clearPassword">
              Clear Credential
            </v-btn>
          </div>
        </div>
      </div>

      <div class="adminGroup">
        <div class="adminGroupHeader">
          <h3>Message</h3>
        </div>
        <div class="adminCard">
          <v-text-field
            v-model="draft.fromAddress"
            label="From Address"
            placeholder="codex@example.com"
            hint="Falls back to the SMTP username when blank."
            :rules="emailRules"
            persistent-hint
            hide-details="auto"
            density="compact"
          />
        </div>
        <div class="adminCard">
          <v-text-field
            v-model="draft.subjectPrefix"
            label="Subject Prefix"
            hide-details="auto"
            density="compact"
          />
        </div>
      </div>

      <div class="settingsActions">
        <v-btn
          type="submit"
          variant="tonal"
          size="small"
          :loading="saving"
          :disabled="!hasChanges"
        >
          Save Settings
        </v-btn>
        <v-btn
          variant="text"
          size="small"
          :disabled="!hasChanges || saving"
          @click="resetDraft"
        >
          Revert
        </v-btn>
      </div>

      <div class="adminGroup">
        <div class="adminGroupHeader">
          <h3>Test Send</h3>
        </div>
        <div class="adminCard">
          <div class="credentialFields">
            <v-text-field
              v-model="testRecipient"
              label="Recipient"
              placeholder="you@example.com"
              type="email"
              :rules="recipientRules"
              hide-details="auto"
              density="compact"
            />
            <div class="credentialActions">
              <v-btn
                variant="tonal"
                size="small"
                :loading="testing"
                :disabled="!canTest"
                @click="runTest"
              >
                Send Test
              </v-btn>
            </div>
            <div
              v-if="testResult"
              class="testResult"
              :class="{ ok: testResult.ok, error: !testResult.ok }"
            >
              {{
                testResult.ok
                  ? "Test message sent."
                  : testResult.error || "Test send failed."
              }}
            </div>
          </div>
        </div>
      </div>
    </v-form>
  </div>
</template>

<script>
import { dequal } from "dequal";
import { mapActions, mapState } from "pinia";

import { useAdminStore } from "@/stores/admin";

const EDITABLE_FIELDS = Object.freeze([
  "host",
  "port",
  "useTls",
  "useSsl",
  "timeout",
  "user",
  "fromAddress",
  "subjectPrefix",
]);
// Simple hostname/FQDN regex: at least one ``.``, no whitespace.
const HOST_REGEX = /^\S+\.\S+$/;
const EMAIL_REGEX = /^\S+@\S+\.\S+$/;
const PORT_MIN = 1;
const PORT_MAX = 65_535;
const TIMEOUT_MIN = 1;
const TIMEOUT_MAX = 600;

function pickFields(source) {
  const out = {};
  for (const key of EDITABLE_FIELDS) {
    out[key] = source?.[key] ?? "";
  }
  return out;
}

export default {
  name: "AdminEmailTab",
  data() {
    return {
      draft: pickFields(undefined),
      passwordDraft: "",
      testRecipient: "",
      testing: false,
      testResult: undefined,
      saving: false,
    };
  },
  computed: {
    ...mapState(useAdminStore, {
      settings: (state) => state.emailSettings,
    }),
    canTest() {
      return Boolean(this.testRecipient && this.draft?.host);
    },
    hasChanges() {
      if (this.passwordDraft) return true;
      return !dequal(this.draft, pickFields(this.settings));
    },
    passwordHint() {
      if (this.passwordDraft) {
        return "Will be saved with the rest of the SMTP settings.";
      }
      return this.settings.passwordSet ? "Credential set" : "Not configured";
    },
    hostRules() {
      return [(v) => !v || HOST_REGEX.test(v) || "Enter a valid hostname"];
    },
    portRules() {
      return [
        (v) => {
          if (v === "" || v === null || v === undefined) return true;
          const n = Number(v);
          return (
            (Number.isInteger(n) && n >= PORT_MIN && n <= PORT_MAX) ||
            `Port must be between ${PORT_MIN} and ${PORT_MAX}`
          );
        },
      ];
    },
    timeoutRules() {
      return [
        (v) => {
          if (v === "" || v === null || v === undefined) return true;
          const n = Number(v);
          return (
            (Number.isInteger(n) && n >= TIMEOUT_MIN && n <= TIMEOUT_MAX) ||
            `Timeout must be between ${TIMEOUT_MIN} and ${TIMEOUT_MAX} seconds`
          );
        },
      ];
    },
    emailRules() {
      return [
        (v) => !v || EMAIL_REGEX.test(v) || "Enter a valid email address",
      ];
    },
    recipientRules() {
      return [
        (v) => !!v || "Recipient is required",
        (v) => EMAIL_REGEX.test(v) || "Enter a valid email address",
      ];
    },
  },
  watch: {
    settings: {
      immediate: true,
      handler(value) {
        this.draft = pickFields(value);
      },
    },
  },
  mounted() {
    this.loadEmailSettings();
  },
  methods: {
    ...mapActions(useAdminStore, [
      "loadEmailSettings",
      "updateEmailSettings",
      "sendEmailTest",
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
      if (this.passwordDraft) {
        payload.password = this.passwordDraft;
      }
      this.saving = true;
      try {
        await this.updateEmailSettings(payload);
        this.passwordDraft = "";
      } finally {
        this.saving = false;
      }
    },
    clearPassword() {
      if (!confirm("Clear SMTP credential?")) return;
      this.updateEmailSettings({ password: "" });
    },
    async runTest() {
      this.testing = true;
      this.testResult = undefined;
      try {
        const result = await this.sendEmailTest({
          recipient: this.testRecipient,
        });
        this.testResult = result;
      } finally {
        this.testing = false;
      }
    },
  },
};
</script>

<style scoped lang="scss">
@use "@/components/admin/tabs/admin-section.scss";

.adminIntro {
  max-width: 720px;
  margin-bottom: 16px;
  font-size: 0.9em;
  color: rgb(var(--v-theme-textSecondary));
}

.adminIntro p {
  margin-bottom: 8px;
}

.adminIntro ul {
  margin: 0 0 8px 24px;
  padding: 0;
}

.adminIntro li {
  margin-bottom: 4px;
}

.credentialFields {
  display: flex;
  flex-direction: column;
  gap: 8px;
  padding-top: 8px;
}

.credentialActions {
  display: flex;
  gap: 8px;
  align-items: center;
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

.settingsActions {
  display: flex;
  gap: 8px;
  align-items: center;
  margin: 0 0 16px;
}

.smtpUsernameProxy {
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

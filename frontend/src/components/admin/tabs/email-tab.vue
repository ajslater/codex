<template>
  <div id="email" class="adminReadingColumn">
    <div v-if="!settings">
      <v-progress-circular indeterminate />
    </div>
    <v-form v-else ref="form" @submit.prevent="saveDraft">
      <div class="adminProse">
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

      <AdminSection title="SMTP Server">
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
      </AdminSection>

      <AdminSection title="Authentication">
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
          <div v-if="settings.passwordSet" class="adminInlineActions">
            <ConfirmDialog
              button-text="Clear Credential"
              title-text="Clear SMTP Credential"
              text="Clear the saved SMTP password or token?"
              confirm-text="Clear"
              variant="text"
              size="small"
              :block="false"
              @confirm="clearPassword"
            />
          </div>
        </div>
      </AdminSection>

      <AdminSection title="Message">
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
      </AdminSection>

      <AdminActionBar
        save-text="Save Settings"
        :saving="saving"
        :save-disabled="!hasChanges"
        :revert-disabled="!hasChanges || saving"
        @revert="resetDraft"
      />

      <AdminSection title="Test Send">
        <div class="adminCard">
          <div class="adminFieldColumn">
            <v-text-field
              v-model="testRecipient"
              label="Recipient"
              placeholder="you@example.com"
              type="email"
              :rules="recipientRules"
              hide-details="auto"
              density="compact"
            />
            <div class="adminInlineActions">
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
      </AdminSection>
    </v-form>
  </div>
</template>

<script>
import { dequal } from "dequal";
import { mapActions, mapState } from "pinia";

import AdminActionBar from "@/components/admin/tabs/action-bar.vue";
import AdminSection from "@/components/admin/tabs/admin-section.vue";
import ConfirmDialog from "@/components/confirm-dialog.vue";
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
  components: {
    AdminActionBar,
    AdminSection,
    ConfirmDialog,
  },
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

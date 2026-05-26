<template>
  <div id="email" class="adminContainer">
    <div v-if="!settings" class="adminGroup">
      <v-progress-circular indeterminate />
    </div>
    <template v-else>
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
            :model-value="settings.host"
            label="Host"
            placeholder="smtp.example.com"
            hide-details="auto"
            density="compact"
            @update:model-value="save('host', $event)"
          />
        </div>
        <div class="adminCard">
          <v-text-field
            :model-value="settings.port"
            type="number"
            label="Port"
            min="1"
            max="65535"
            hide-details="auto"
            density="compact"
            @update:model-value="save('port', toInt($event))"
          />
        </div>
        <div class="adminCard">
          <v-checkbox
            :model-value="settings.useTls"
            label="STARTTLS"
            density="compact"
            hide-details="auto"
            @update:model-value="save('useTls', $event)"
          />
        </div>
        <div class="adminCard">
          <v-checkbox
            :model-value="settings.useSsl"
            label="SSL on connect"
            density="compact"
            hide-details="auto"
            @update:model-value="save('useSsl', $event)"
          />
        </div>
        <div class="adminCard">
          <v-text-field
            :model-value="settings.timeout"
            type="number"
            label="Timeout (seconds)"
            min="1"
            max="600"
            hide-details="auto"
            density="compact"
            @update:model-value="save('timeout', toInt($event))"
          />
        </div>
      </div>

      <div class="adminGroup">
        <div class="adminGroupHeader">
          <h3>Authentication</h3>
        </div>
        <div class="adminCard">
          <v-text-field
            :model-value="settings.user"
            label="Username"
            hide-details="auto"
            density="compact"
            autocomplete="off"
            @update:model-value="save('user', $event)"
          />
        </div>
        <v-expansion-panels
          :model-value="settings.passwordSet ? [] : [0]"
          variant="accordion"
        >
          <v-expansion-panel>
            <v-expansion-panel-title>
              <span class="adminCardTitle">Password</span>
              <span
                class="adminCardDesc"
                :class="{ credentialSet: settings.passwordSet }"
              >
                {{ settings.passwordSet ? "Password set" : "Not configured" }}
              </span>
            </v-expansion-panel-title>
            <v-expansion-panel-text>
              <!--
                Wrapping the password input in a ``<form>`` keeps
                browser DOM password-field heuristics happy (the
                console warning "Password field is not contained in a
                form" goes away) and lets password managers offer to
                save the credential. ``@submit.prevent`` suppresses
                default Enter-submit since the Save button drives the
                actual write via ``savePassword``.
              -->
              <form
                class="credentialFields"
                autocomplete="off"
                @submit.prevent="savePassword"
              >
                <v-text-field
                  v-model="passwordDraft"
                  label="Password"
                  type="password"
                  autocomplete="new-password"
                  hide-details="auto"
                  density="compact"
                  :placeholder="
                    settings.passwordSet ? 'New Password' : 'Enter password'
                  "
                />
                <div class="credentialActions">
                  <v-btn
                    type="submit"
                    variant="tonal"
                    size="small"
                    :disabled="!passwordDraft"
                  >
                    Save Password
                  </v-btn>
                  <v-btn
                    v-if="settings.passwordSet"
                    variant="text"
                    size="small"
                    @click="clearPassword"
                  >
                    Clear Password
                  </v-btn>
                </div>
              </form>
            </v-expansion-panel-text>
          </v-expansion-panel>
        </v-expansion-panels>
      </div>

      <div class="adminGroup">
        <div class="adminGroupHeader">
          <h3>Message</h3>
        </div>
        <div class="adminCard">
          <v-text-field
            :model-value="settings.fromAddress"
            label="From Address"
            placeholder="codex@example.com"
            hint="Falls back to the SMTP username when blank."
            persistent-hint
            hide-details="auto"
            density="compact"
            @update:model-value="save('fromAddress', $event)"
          />
        </div>
        <div class="adminCard">
          <v-text-field
            :model-value="settings.subjectPrefix"
            label="Subject Prefix"
            hide-details="auto"
            density="compact"
            @update:model-value="save('subjectPrefix', $event)"
          />
        </div>
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
    </template>
  </div>
</template>

<script>
import { mapActions, mapState } from "pinia";

import { useAdminStore } from "@/stores/admin";

export default {
  name: "AdminEmailTab",
  data() {
    return {
      passwordDraft: "",
      testRecipient: "",
      testing: false,
      testResult: undefined,
    };
  },
  computed: {
    ...mapState(useAdminStore, {
      settings: (state) => state.emailSettings,
    }),
    canTest() {
      return Boolean(this.testRecipient && this.settings?.host);
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
    save(field, value) {
      this.updateEmailSettings({ [field]: value });
    },
    toInt(value) {
      const n = Number.parseInt(value, 10);
      return Number.isFinite(n) ? n : 0;
    },
    savePassword() {
      if (!this.passwordDraft) return;
      this.updateEmailSettings({ password: this.passwordDraft }).then(() => {
        this.passwordDraft = "";
      });
    },
    clearPassword() {
      if (!confirm("Clear SMTP password?")) return;
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

.credentialSet {
  color: rgb(var(--v-theme-success));
}

.adminCardDesc {
  margin-left: 8px;
  font-size: 0.85em;
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
</style>

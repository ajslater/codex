<template>
  <div id="email" class="adminContainer">
    <div v-if="!settings" class="adminGroup">
      <v-progress-circular indeterminate />
    </div>
    <template v-else>
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
              <div class="credentialFields">
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
                    variant="tonal"
                    size="small"
                    :disabled="!passwordDraft"
                    @click="savePassword"
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
              </div>
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

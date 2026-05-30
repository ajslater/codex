<template>
  <div id="tagging" class="adminReadingColumn">
    <div v-if="!defaults">
      <v-progress-circular indeterminate />
    </div>
    <template v-else>
      <v-form ref="form" @submit.prevent="saveDraft">
        <AdminSection title="Write Defaults">
          <div class="adminCard">
            <v-select
              v-model="draft.defaultFormats"
              :items="formatChoices"
              label="Metadata Formats"
              hide-details="auto"
              density="compact"
              multiple
              chips
            />
          </div>
          <div class="adminCard">
            <v-checkbox
              v-model="draft.deleteOriginal"
              label="Delete original after converting to CBZ"
              :hint="deleteOriginalHint"
              persistent-hint
              density="compact"
            />
          </div>
        </AdminSection>

        <AdminSection title="Online Tagging Defaults">
          <div class="adminCard">
            <v-select
              v-model="draft.defaultMatchMode"
              :items="matchModeChoices"
              label="Match Mode"
              hide-details="auto"
              density="compact"
            />
          </div>
          <div class="adminCard">
            <v-select
              v-model="draft.defaultPromptsMode"
              :items="promptsModeChoices"
              label="Prompts"
              hide-details="auto"
              density="compact"
            />
          </div>
          <div class="adminCard">
            <v-select
              v-model="draft.defaultSources"
              :items="sourceItems"
              label="Online Sources"
              hide-details="auto"
              density="compact"
              multiple
              chips
            />
          </div>
          <div class="adminCard">
            <TimeoutInput
              v-model="draft.promptTimeoutSeconds"
              label="Prompt Timeout"
            />
          </div>
        </AdminSection>

        <AdminActionBar
          save-text="Save Defaults"
          :saving="saving"
          :save-disabled="!hasChanges"
          :revert-disabled="!hasChanges || saving"
          @revert="resetDraft"
        />
      </v-form>

      <AdminSection title="Online Source Credentials">
        <v-expansion-panels
          :model-value="defaults.hasMetronCredentials ? [] : [0]"
          variant="accordion"
        >
          <v-expansion-panel>
            <v-expansion-panel-title>
              <span class="adminCardTitle">Metron</span>
              <span
                class="adminCardDesc credentialStatus"
                :class="{ credentialSet: defaults.hasMetronCredentials }"
              >
                {{
                  defaults.hasMetronCredentials
                    ? "Credentials set"
                    : "Not configured"
                }}
              </span>
            </v-expansion-panel-title>
            <v-expansion-panel-text>
              <div class="adminFieldColumn">
                <v-text-field
                  v-model="metronUser"
                  label="Username"
                  hide-details="auto"
                  density="compact"
                  :placeholder="
                    defaults.metronUserSet ? 'New Username' : 'Enter username'
                  "
                />
                <v-text-field
                  v-model="metronPassword"
                  label="Password"
                  type="password"
                  hide-details="auto"
                  density="compact"
                  :placeholder="
                    defaults.metronPasswordSet
                      ? 'New Password'
                      : 'Enter password'
                  "
                />
                <v-text-field
                  v-model="metronUrlLocal"
                  label="Custom URL (optional)"
                  hide-details="auto"
                  density="compact"
                  :placeholder="defaults.metronUrl || 'Default'"
                />
                <div class="adminInlineActions">
                  <v-btn
                    variant="tonal"
                    size="small"
                    :disabled="
                      !metronUser && !metronPassword && !metronUrlLocal
                    "
                    @click="saveMetronCredentials"
                  >
                    Save Metron Credentials
                  </v-btn>
                  <v-btn
                    variant="text"
                    size="small"
                    :loading="validating.metron"
                    :disabled="!canTestMetron"
                    @click="testMetronCredentials"
                  >
                    Test
                  </v-btn>
                  <ConfirmDialog
                    v-if="defaults.hasMetronCredentials"
                    button-text="Clear Credentials"
                    title-text="Clear Metron Credentials"
                    text="Remove the saved Metron username, password, and custom URL?"
                    confirm-text="Clear"
                    variant="text"
                    size="small"
                    :block="false"
                    @confirm="clearMetronCredentials"
                  />
                </div>
                <ValidationChip
                  v-if="validationResult.metron"
                  :result="validationResult.metron"
                />
              </div>
            </v-expansion-panel-text>
          </v-expansion-panel>
        </v-expansion-panels>
        <v-expansion-panels
          :model-value="defaults.hasComicvineCredentials ? [] : [0]"
          variant="accordion"
        >
          <v-expansion-panel>
            <v-expansion-panel-title>
              <span class="adminCardTitle">Comic Vine</span>
              <span
                class="adminCardDesc credentialStatus"
                :class="{ credentialSet: defaults.hasComicvineCredentials }"
              >
                {{
                  defaults.hasComicvineCredentials
                    ? "API key set"
                    : "Not configured"
                }}
              </span>
            </v-expansion-panel-title>
            <v-expansion-panel-text>
              <div class="adminFieldColumn">
                <v-text-field
                  v-model="comicvineKey"
                  label="API Key"
                  type="password"
                  hide-details="auto"
                  density="compact"
                  :placeholder="
                    defaults.comicvineKeySet ? 'New API Key' : 'Enter API key'
                  "
                />
                <v-text-field
                  v-model="comicvineUrlLocal"
                  label="Custom URL (optional)"
                  hide-details="auto"
                  density="compact"
                  :placeholder="defaults.comicvineUrl || 'Default'"
                />
                <div class="adminInlineActions">
                  <v-btn
                    variant="tonal"
                    size="small"
                    :disabled="!comicvineKey && !comicvineUrlLocal"
                    @click="saveComicvineCredentials"
                  >
                    Save Comic Vine Credentials
                  </v-btn>
                  <v-btn
                    variant="text"
                    size="small"
                    :loading="validating.comicvine"
                    :disabled="!canTestComicvine"
                    @click="testComicvineCredentials"
                  >
                    Test
                  </v-btn>
                  <ConfirmDialog
                    v-if="defaults.hasComicvineCredentials"
                    button-text="Clear API Key"
                    title-text="Clear Comic Vine API Key"
                    text="Remove the saved Comic Vine API key and custom URL?"
                    confirm-text="Clear"
                    variant="text"
                    size="small"
                    :block="false"
                    @confirm="clearComicvineCredentials"
                  />
                </div>
                <ValidationChip
                  v-if="validationResult.comicvine"
                  :result="validationResult.comicvine"
                />
              </div>
            </v-expansion-panel-text>
          </v-expansion-panel>
        </v-expansion-panels>
      </AdminSection>
    </template>
  </div>
</template>

<script>
import { dequal } from "dequal";
import { mapActions, mapState } from "pinia";

import TAGGING_CHOICES from "@/choices/tagging-choices.json";
import AdminActionBar from "@/components/admin/tabs/action-bar.vue";
import AdminSection from "@/components/admin/tabs/admin-section.vue";
import TimeoutInput from "@/components/admin/tabs/timeout-input.vue";
import ValidationChip from "@/components/admin/tabs/tagging-validation-chip.vue";
import ConfirmDialog from "@/components/confirm-dialog.vue";
import { useAdminStore } from "@/stores/admin";

const FORMAT_CHOICES = [
  { title: "MetronInfo", value: "METRON_INFO" },
  { title: "ComicInfo", value: "COMIC_INFO" },
];

const EDITABLE_FIELDS = Object.freeze([
  "defaultFormats",
  "deleteOriginal",
  "defaultMatchMode",
  "defaultPromptsMode",
  "defaultSources",
  "promptTimeoutSeconds",
]);

function pickFields(source) {
  const out = {};
  for (const key of EDITABLE_FIELDS) {
    const value = source?.[key];
    out[key] = Array.isArray(value) ? [...value] : (value ?? null);
  }
  return out;
}

export default {
  name: "AdminTaggingTab",
  components: {
    AdminActionBar,
    AdminSection,
    ConfirmDialog,
    TimeoutInput,
    ValidationChip,
  },
  data() {
    return {
      formatChoices: FORMAT_CHOICES,
      matchModeChoices: TAGGING_CHOICES.matchMode,
      promptsModeChoices: TAGGING_CHOICES.promptsMode,
      draft: pickFields(undefined),
      saving: false,
      metronUser: "",
      metronPassword: "",
      metronUrlLocal: "",
      comicvineKey: "",
      comicvineUrlLocal: "",
      validating: { metron: false, comicvine: false },
      validationResult: { metron: undefined, comicvine: undefined },
    };
  },
  computed: {
    ...mapState(useAdminStore, {
      defaults: (state) => state.taggingDefaults,
    }),
    hasChanges() {
      return !dequal(this.draft, pickFields(this.defaults));
    },
    deleteOriginalHint() {
      return "Writing tags to CBR, CB7, or CBT archives converts them to CBZ. Enable this to delete the original file after conversion.";
    },
    sourceItems() {
      return [
        {
          title: "Metron",
          value: "metron",
          props: this.defaults?.hasMetronCredentials ? {} : { disabled: true },
        },
        {
          title: "Comic Vine",
          value: "comicvine",
          props: this.defaults?.hasComicvineCredentials
            ? {}
            : { disabled: true },
        },
      ];
    },
    canTestMetron() {
      const formHasUser = Boolean(this.metronUser);
      const formHasPassword = Boolean(this.metronPassword);
      const storedUser = Boolean(this.defaults?.metronUserSet);
      const storedPassword = Boolean(this.defaults?.metronPasswordSet);
      return (formHasUser || storedUser) && (formHasPassword || storedPassword);
    },
    canTestComicvine() {
      return (
        Boolean(this.comicvineKey) || Boolean(this.defaults?.comicvineKeySet)
      );
    },
  },
  watch: {
    defaults: {
      immediate: true,
      handler(value) {
        this.draft = pickFields(value);
      },
    },
  },
  mounted() {
    this.loadTaggingDefaults();
  },
  methods: {
    ...mapActions(useAdminStore, [
      "loadTaggingDefaults",
      "updateTaggingDefaults",
      "validateTaggingCredentials",
    ]),
    resetDraft() {
      this.draft = pickFields(this.defaults);
    },
    async saveDraft() {
      const form = this.$refs.form;
      if (form) {
        const { valid } = await form.validate();
        if (!valid) return;
      }
      this.saving = true;
      try {
        await this.updateTaggingDefaults({ ...this.draft });
      } finally {
        this.saving = false;
      }
    },
    saveMetronCredentials() {
      const data = {};
      if (this.metronUser) data.metronUser = this.metronUser;
      if (this.metronPassword) data.metronPassword = this.metronPassword;
      if (this.metronUrlLocal) data.metronUrl = this.metronUrlLocal;
      this.validationResult.metron = undefined;
      this.updateTaggingDefaults(data).then(() => {
        this.metronUser = "";
        this.metronPassword = "";
        this.metronUrlLocal = "";
      });
    },
    saveComicvineCredentials() {
      const data = {};
      if (this.comicvineKey) data.comicvineKey = this.comicvineKey;
      if (this.comicvineUrlLocal) data.comicvineUrl = this.comicvineUrlLocal;
      this.validationResult.comicvine = undefined;
      this.updateTaggingDefaults(data).then(() => {
        this.comicvineKey = "";
        this.comicvineUrlLocal = "";
      });
    },
    clearMetronCredentials() {
      this.validationResult.metron = undefined;
      this.updateTaggingDefaults({
        metronUser: "",
        metronPassword: "",
        metronUrl: "",
      });
    },
    clearComicvineCredentials() {
      this.validationResult.comicvine = undefined;
      this.updateTaggingDefaults({
        comicvineKey: "",
        comicvineUrl: "",
      });
    },
    async testMetronCredentials() {
      const payload = { source: "metron" };
      if (this.metronUser) payload.metronUser = this.metronUser;
      if (this.metronPassword) payload.metronPassword = this.metronPassword;
      if (this.metronUrlLocal) payload.metronUrl = this.metronUrlLocal;
      await this._runValidation("metron", payload);
    },
    async testComicvineCredentials() {
      const payload = { source: "comicvine" };
      if (this.comicvineKey) payload.comicvineKey = this.comicvineKey;
      if (this.comicvineUrlLocal) payload.comicvineUrl = this.comicvineUrlLocal;
      await this._runValidation("comicvine", payload);
    },
    async _runValidation(source, payload) {
      this.validating[source] = true;
      this.validationResult[source] = undefined;
      try {
        const results = await this.validateTaggingCredentials(payload);
        if (results && results[source]) {
          this.validationResult[source] = results[source];
        }
      } finally {
        this.validating[source] = false;
      }
    },
  },
};
</script>

<style scoped lang="scss">
@use "@/components/admin/tabs/admin-section.scss";
@use "@/components/admin/tabs/design.scss" as d;

.credentialStatus {
  margin-left: d.$space-2;
}

.credentialSet {
  color: rgb(var(--v-theme-success));
}
</style>

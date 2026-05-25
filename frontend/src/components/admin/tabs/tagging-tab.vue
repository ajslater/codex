<template>
  <div id="tagging" class="adminContainer">
    <div v-if="!defaults" class="adminGroup">
      <v-progress-circular indeterminate />
    </div>
    <template v-else>
      <!-- Write Defaults -->
      <div class="adminGroup">
        <div class="adminGroupHeader">
          <h3>Write Defaults</h3>
        </div>
        <div class="adminCard">
          <v-select
            :model-value="defaults.defaultFormats"
            :items="formatChoices"
            label="Metadata Formats"
            hide-details="auto"
            density="compact"
            multiple
            chips
            @update:model-value="save('defaultFormats', $event)"
          />
        </div>
        <div class="adminCard">
          <v-checkbox
            :model-value="defaults.deleteOriginal"
            label="Delete original after converting to CBZ"
            :hint="deleteOriginalHint"
            persistent-hint
            density="compact"
            @update:model-value="save('deleteOriginal', $event)"
          />
        </div>
      </div>

      <!-- Online Defaults -->
      <div class="adminGroup">
        <div class="adminGroupHeader">
          <h3>Online Tagging Defaults</h3>
        </div>
        <div class="adminCard">
          <v-select
            :model-value="defaults.defaultMatchMode"
            :items="matchModeChoices"
            label="Match Mode"
            hide-details="auto"
            density="compact"
            @update:model-value="save('defaultMatchMode', $event)"
          />
        </div>
        <div class="adminCard">
          <v-select
            :model-value="defaults.defaultPromptsMode"
            :items="promptsModeChoices"
            label="Prompts"
            hide-details="auto"
            density="compact"
            @update:model-value="save('defaultPromptsMode', $event)"
          />
        </div>
        <div class="adminCard">
          <v-select
            :model-value="defaults.defaultSources"
            :items="sourceItems"
            label="Online Sources"
            hide-details="auto"
            density="compact"
            multiple
            chips
            @update:model-value="save('defaultSources', $event)"
          />
        </div>
        <div class="adminCard">
          <TimeoutInput
            label="Prompt Timeout"
            :model-value="defaults.promptTimeoutSeconds"
            @update:model-value="save('promptTimeoutSeconds', $event)"
          />
        </div>
      </div>

      <!-- Credentials -->
      <div class="adminGroup">
        <div class="adminGroupHeader">
          <h3>Online Source Credentials</h3>
        </div>
        <v-expansion-panels
          :model-value="defaults.hasMetronCredentials ? [] : [0]"
          variant="accordion"
        >
          <v-expansion-panel>
            <v-expansion-panel-title>
              <span class="adminCardTitle">Metron</span>
              <span
                class="adminCardDesc"
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
              <div class="credentialFields">
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
                <div class="credentialActions">
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
                  <v-btn
                    v-if="defaults.hasMetronCredentials"
                    variant="text"
                    size="small"
                    @click="clearMetronCredentials"
                  >
                    Clear Credentials
                  </v-btn>
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
                class="adminCardDesc"
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
              <div class="credentialFields">
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
                <div class="credentialActions">
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
                  <v-btn
                    v-if="defaults.hasComicvineCredentials"
                    variant="text"
                    size="small"
                    @click="clearComicvineCredentials"
                  >
                    Clear API Key
                  </v-btn>
                </div>
                <ValidationChip
                  v-if="validationResult.comicvine"
                  :result="validationResult.comicvine"
                />
              </div>
            </v-expansion-panel-text>
          </v-expansion-panel>
        </v-expansion-panels>
      </div>
    </template>
  </div>
</template>

<script>
import { mapActions, mapState } from "pinia";

import TAGGING_CHOICES from "@/choices/tagging-choices.json";
import TimeoutInput from "@/components/admin/tabs/timeout-input.vue";
import ValidationChip from "@/components/admin/tabs/tagging-validation-chip.vue";
import { useAdminStore } from "@/stores/admin";

const FORMAT_CHOICES = [
  { title: "MetronInfo", value: "METRON_INFO" },
  { title: "ComicInfo", value: "COMIC_INFO" },
];

export default {
  name: "AdminTaggingTab",
  components: {
    TimeoutInput,
    ValidationChip,
  },
  data() {
    return {
      formatChoices: FORMAT_CHOICES,
      matchModeChoices: TAGGING_CHOICES.matchMode,
      promptsModeChoices: TAGGING_CHOICES.promptsMode,
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
  mounted() {
    this.loadTaggingDefaults();
  },
  methods: {
    ...mapActions(useAdminStore, [
      "loadTaggingDefaults",
      "updateTaggingDefaults",
      "validateTaggingCredentials",
    ]),
    save(field, value) {
      this.updateTaggingDefaults({ [field]: value });
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
      if (!confirm("Clear Metron credentials?")) return;
      this.validationResult.metron = undefined;
      this.updateTaggingDefaults({
        metronUser: "",
        metronPassword: "",
        metronUrl: "",
      });
    },
    clearComicvineCredentials() {
      if (!confirm("Clear Comic Vine API key?")) return;
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

.credentialSet {
  color: rgb(var(--v-theme-success));
}

.adminCardDesc {
  margin-left: 8px;
  font-size: 0.85em;
}

.credentialActions {
  display: flex;
  gap: 8px;
  align-items: center;
}

.credentialFields {
  display: flex;
  flex-direction: column;
  gap: 8px;
  padding-top: 8px;
}
</style>

<template>
  <div id="tagging" class="adminReadingColumn">
    <div v-if="!defaults">
      <v-progress-circular indeterminate />
    </div>
    <template v-else>
      <TaggingStatusTable />
      <v-form @submit.prevent>
        <AdminSection title="Tagging Defaults">
          <template #hint>
            Tags are written directly into your comic files, so the comics
            directory must be on a writable filesystem and Codex must have
            permission to write to it. Read-only mounts cause tag writes to
            fail.
          </template>
          <div class="adminCard">
            <v-select
              v-model="draft.defaultFormats"
              :items="formatChoices"
              label="Metadata Formats"
              :hint="metadataFormatsHint"
              persistent-hint
              hide-details="auto"
              density="compact"
              multiple
              chips
            >
              <!-- Render the hint via the message slot so the docs links live
                   inside the field's own hint, styled like every other. -->
              <template #message>
                These metadata formats are written into each comic every time
                its tags are edited. Learn more about
                <a
                  href="https://anansi-project.github.io/docs/category/comicinfo"
                  target="_blank"
                  >ComicInfo<v-icon size="small">{{ mdiOpenInNew }}</v-icon></a
                >
                and
                <a
                  href="https://metron-project.github.io/docs/category/metroninfo"
                  target="_blank"
                  >MetronInfo<v-icon size="small">{{ mdiOpenInNew }}</v-icon></a
                >.
              </template>
            </v-select>
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
              :hint="matchModeHint"
              persistent-hint
              hide-details="auto"
              density="compact"
            />
          </div>
          <div class="adminCard">
            <v-select
              v-model="draft.defaultPromptsMode"
              :items="promptsModeChoices"
              label="Prompts"
              :hint="promptsModeHint"
              persistent-hint
              hide-details="auto"
              density="compact"
            />
          </div>
        </AdminSection>

        <AdminSection title="Online Tagging Sources">
          <p class="adminHint sourcesHint">
            {{ sourcesOrderHint }}
          </p>
          <div class="sourcesGroup">
            <div class="sourceRow" :style="sourceRowStyle('metron')">
              <div
                class="sourceEnable"
                :title="
                  defaults.hasMetronCredentials ? '' : sourceDisabledTooltip
                "
              >
                <v-checkbox
                  v-model="metronEnabled"
                  :disabled="!defaults.hasMetronCredentials"
                  aria-label="Enable Metron Cloud"
                  hide-details
                  density="compact"
                />
                <div v-if="metronEnabled" class="sourceOrderButtons">
                  <v-btn
                    icon
                    variant="text"
                    density="compact"
                    aria-label="Raise Metron Cloud priority"
                    :disabled="sourcePriority('metron') <= 0"
                    @click="moveSource('metron', -1)"
                  >
                    <v-icon>{{ mdiChevronUp }}</v-icon>
                  </v-btn>
                  <v-btn
                    icon
                    variant="text"
                    density="compact"
                    aria-label="Lower Metron Cloud priority"
                    :disabled="
                      sourcePriority('metron') >=
                      (draft.defaultSources || []).length - 1
                    "
                    @click="moveSource('metron', 1)"
                  >
                    <v-icon>{{ mdiChevronDown }}</v-icon>
                  </v-btn>
                </div>
              </div>
              <div class="sourcePanel">
                <v-expansion-panels
                  :model-value="defaults.hasMetronCredentials ? [] : [0]"
                  variant="accordion"
                >
                  <v-expansion-panel>
                    <v-expansion-panel-title>
                      <span class="adminCardTitle">Metron Cloud</span>
                      <span
                        class="adminCardDesc credentialStatus"
                        :class="{
                          credentialSet: defaults.hasMetronCredentials,
                        }"
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
                            defaults.metronUserSet
                              ? 'New Username'
                              : 'Enter username'
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
                        <p class="adminHint">
                          Get a username and password from
                          <a
                            href="https://metron.cloud/accounts/signup/"
                            target="_blank"
                            >Metron Cloud<v-icon size="small">{{
                              mdiOpenInNew
                            }}</v-icon></a
                          >
                        </p>
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
                            Save Metron Cloud Credentials
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
                            title-text="Clear Metron Cloud Credentials"
                            text="Remove the saved Metron Cloud username, password, and custom URL?"
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
              </div>
            </div>

            <div class="sourceRow" :style="sourceRowStyle('comicvine')">
              <div
                class="sourceEnable"
                :title="
                  defaults.hasComicvineCredentials ? '' : sourceDisabledTooltip
                "
              >
                <v-checkbox
                  v-model="comicvineEnabled"
                  :disabled="!defaults.hasComicvineCredentials"
                  aria-label="Enable Comic Vine"
                  hide-details
                  density="compact"
                />
                <div v-if="comicvineEnabled" class="sourceOrderButtons">
                  <v-btn
                    icon
                    variant="text"
                    density="compact"
                    aria-label="Raise Comic Vine priority"
                    :disabled="sourcePriority('comicvine') <= 0"
                    @click="moveSource('comicvine', -1)"
                  >
                    <v-icon>{{ mdiChevronUp }}</v-icon>
                  </v-btn>
                  <v-btn
                    icon
                    variant="text"
                    density="compact"
                    aria-label="Lower Comic Vine priority"
                    :disabled="
                      sourcePriority('comicvine') >=
                      (draft.defaultSources || []).length - 1
                    "
                    @click="moveSource('comicvine', 1)"
                  >
                    <v-icon>{{ mdiChevronDown }}</v-icon>
                  </v-btn>
                </div>
              </div>
              <div class="sourcePanel">
                <v-expansion-panels
                  :model-value="defaults.hasComicvineCredentials ? [] : [0]"
                  variant="accordion"
                >
                  <v-expansion-panel>
                    <v-expansion-panel-title>
                      <span class="adminCardTitle">Comic Vine</span>
                      <span
                        class="adminCardDesc credentialStatus"
                        :class="{
                          credentialSet: defaults.hasComicvineCredentials,
                        }"
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
                            defaults.comicvineKeySet
                              ? 'New API Key'
                              : 'Enter API key'
                          "
                        />
                        <p class="adminHint">
                          Get an API key from the
                          <a
                            href="https://comicvine.gamespot.com/api/"
                            target="_blank"
                            >Comic Vine API<v-icon size="small">{{
                              mdiOpenInNew
                            }}</v-icon></a
                          >
                        </p>
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
              </div>
            </div>
          </div>
          <div class="adminCard mergeAllSourcesCard">
            <v-checkbox
              v-model="draft.mergeAllSources"
              label="Merge all sources"
              :hint="mergeAllSourcesHint"
              :disabled="!canMerge"
              persistent-hint
              hide-details="auto"
              density="compact"
            />
          </div>
        </AdminSection>
      </v-form>
      <TagWriteErrorsPanel />
    </template>
  </div>
</template>

<script>
import { mdiChevronDown, mdiChevronUp, mdiOpenInNew } from "@mdi/js";
import { dequal } from "dequal";
import { mapActions, mapState } from "pinia";

import TAGGING_CHOICES from "@/choices/tagging-choices.json";
import AdminSection from "@/components/admin/tabs/admin-section.vue";
import TaggingStatusTable from "@/components/admin/tabs/tagging-status-table.vue";
import TagWriteErrorsPanel from "@/components/admin/tabs/tag-write-errors-panel.vue";
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
  "mergeAllSources",
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
    AdminSection,
    ConfirmDialog,
    TaggingStatusTable,
    TagWriteErrorsPanel,
    ValidationChip,
  },
  data() {
    return {
      mdiChevronDown,
      mdiChevronUp,
      mdiOpenInNew,
      formatChoices: FORMAT_CHOICES,
      matchModeChoices: TAGGING_CHOICES.matchMode,
      promptsModeChoices: TAGGING_CHOICES.promptsMode,
      metadataFormatsHint:
        "These metadata formats are written into each comic every time its tags are edited. Learn more about ComicInfo and MetronInfo.",
      deleteOriginalHint:
        "Writing tags to CBR, CB7, or CBT archives converts them to CBZ. Enable this to delete the original file after conversion.",
      matchModeHint:
        "How aggressively to accept online matches. Careful writes only near-certain matches, Auto also writes confident ones, and Eager also writes weaker best guesses.",
      promptsModeHint:
        "What to do with matches that are too ambiguous to auto-write. Ask saves them as prompts to resolve later; Never skips them, writing only auto-matched comics.",
      sourceDisabledTooltip:
        "A source can only be enabled once its credentials are saved.",
      sourcesOrderHint:
        "Enabled sources run in priority order — use the arrows to reorder. With Merge all sources off, the highest-priority source that finds a match tags the comic and the rest are skipped. With it on, every enabled source is queried for each comic and their results are merged into one record for the most complete metadata.",
      mergeAllSourcesHint:
        "Merging queries every enabled source for each comic instead of stopping at the first match, so it roughly multiplies online API calls by the number of enabled sources — scans take longer and hit rate limits sooner. Can be overridden per scan in the Tag Online dialog.",
      draft: pickFields(undefined),
      saving: false,
      pendingSave: false,
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
    // The Online Sources enable checkboxes drive ``draft.defaultSources``, which
    // auto-saves with the rest of the defaults. A source can only be checked once
    // its credentials exist, so gate the getter on the stored credential flag
    // too — a credential-less source always reads as off-and-disabled.
    metronEnabled: {
      get() {
        return (
          Boolean(this.defaults?.hasMetronCredentials) &&
          (this.draft.defaultSources || []).includes("metron")
        );
      },
      set(value) {
        this.setSourceEnabled("metron", value);
      },
    },
    comicvineEnabled: {
      get() {
        return (
          Boolean(this.defaults?.hasComicvineCredentials) &&
          (this.draft.defaultSources || []).includes("comicvine")
        );
      },
      set(value) {
        this.setSourceEnabled("comicvine", value);
      },
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
    canMerge() {
      // Merging needs at least two enabled sources; with one there's nothing
      // to merge. metronEnabled / comicvineEnabled already gate on credentials.
      return (
        [this.metronEnabled, this.comicvineEnabled].filter(Boolean).length >= 2
      );
    },
  },
  watch: {
    defaults: {
      // Populate the editable draft once, when the defaults first load. The
      // server echoes these fields back unchanged on save, so re-syncing after
      // that would only risk clobbering an edit made while a save is in flight.
      immediate: true,
      handler(value, oldValue) {
        if (!oldValue && value) {
          this.draft = pickFields(value);
        }
      },
    },
    draft: {
      // Auto-save the Tagging Defaults and Online Tagging Defaults sections as
      // soon as a field changes, so the tab needs no Save button.
      deep: true,
      handler() {
        this.autoSave();
      },
    },
  },
  mounted() {
    this.loadTaggingDefaults();
    this.loadTagWriteErrors();
  },
  methods: {
    ...mapActions(useAdminStore, [
      "loadTaggingDefaults",
      "loadTagWriteErrors",
      "updateTaggingDefaults",
      "validateTaggingCredentials",
    ]),
    setSourceEnabled(source, enabled) {
      // defaultSources order is run priority; a newly enabled source
      // joins at the end (lowest priority).
      const sources = (this.draft.defaultSources || []).filter(
        (s) => s !== source,
      );
      if (enabled) {
        sources.push(source);
      }
      this.draft.defaultSources = sources;
    },
    sourcePriority(source) {
      return (this.draft.defaultSources || []).indexOf(source);
    },
    sourceRowStyle(source) {
      // Render rows in priority order via flex order; sources not in the
      // priority list (disabled) sink below the enabled ones.
      const index = this.sourcePriority(source);
      return { order: index === -1 ? 99 : index };
    },
    moveSource(source, delta) {
      const sources = [...(this.draft.defaultSources || [])];
      const from = sources.indexOf(source);
      const to = from + delta;
      if (from === -1 || to < 0 || to >= sources.length) {
        return;
      }
      [sources[from], sources[to]] = [sources[to], sources[from]];
      this.draft.defaultSources = sources;
    },
    async autoSave() {
      // Serialize saves so overlapping requests can't land out of order; if the
      // draft changes again mid-save, save once more when the current one ends.
      if (this.saving) {
        this.pendingSave = true;
        return;
      }
      if (dequal(this.draft, pickFields(this.defaults))) {
        return;
      }
      this.saving = true;
      this.pendingSave = false;
      try {
        await this.updateTaggingDefaults({ ...this.draft });
      } finally {
        this.saving = false;
      }
      if (this.pendingSave) {
        this.autoSave();
      }
    },
    async saveMetronCredentials() {
      const data = {};
      if (this.metronUser) data.metronUser = this.metronUser;
      if (this.metronPassword) data.metronPassword = this.metronPassword;
      if (this.metronUrlLocal) data.metronUrl = this.metronUrlLocal;
      this.validationResult.metron = undefined;
      const hadCredentials = Boolean(this.defaults?.hasMetronCredentials);
      await this.updateTaggingDefaults(data);
      this.metronUser = "";
      this.metronPassword = "";
      this.metronUrlLocal = "";
      // Configuring a brand-new source enables it automatically; re-saving
      // credentials respects the existing checkbox state.
      if (!hadCredentials && this.defaults?.hasMetronCredentials) {
        this.setSourceEnabled("metron", true);
      }
    },
    async saveComicvineCredentials() {
      const data = {};
      if (this.comicvineKey) data.comicvineKey = this.comicvineKey;
      if (this.comicvineUrlLocal) data.comicvineUrl = this.comicvineUrlLocal;
      this.validationResult.comicvine = undefined;
      const hadCredentials = Boolean(this.defaults?.hasComicvineCredentials);
      await this.updateTaggingDefaults(data);
      this.comicvineKey = "";
      this.comicvineUrlLocal = "";
      if (!hadCredentials && this.defaults?.hasComicvineCredentials) {
        this.setSourceEnabled("comicvine", true);
      }
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

.sourcesHint {
  margin-top: d.$space-2;
}

// The body of the Online Tagging Sources section: one row per source.
// Flex column so the rows can be visually reordered by priority via
// the per-row `order` style without moving template blocks.
.sourcesGroup {
  margin-top: d.$space-4;
  display: flex;
  flex-direction: column;
  gap: d.$space-2;
}

// Each source: the enable checkbox to the left of its credential panel.
.sourceRow {
  display: flex;
  align-items: flex-start;
  gap: d.$space-2;
}

// Pin the checkbox to its panel's title bar instead of letting it ride the
// full (expandable) height of the panel.
.sourceEnable {
  flex: 0 0 auto;
  margin-top: d.$space-1;
}

// Priority arrows under the enable checkbox.
.sourceOrderButtons {
  display: flex;
  flex-direction: column;
  align-items: center;
}

.sourcePanel {
  flex: 1 1 auto;
  min-width: 0;
}

.mergeAllSourcesCard {
  margin-top: d.$space-4;
}
</style>

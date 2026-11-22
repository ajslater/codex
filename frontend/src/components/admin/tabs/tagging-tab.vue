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
            <v-checkbox-group
              v-model="draft.defaultFormats"
              label="Metadata Formats"
              :messages="formatsMessages"
              :error-messages="formatsError"
              density="compact"
              inline
            >
              <v-checkbox
                v-for="format in formatChoices"
                :key="format.value"
                :value="format.value"
                :label="format.title"
                :disabled="isFormatDisabled(format.value)"
              />
              <!-- Render the docs hint via the message slot so its links live
                   inside the field's own hint, styled like every other. -->
              <template #message="{ message }">
                <template v-if="message === metadataFormatsHint">
                  These metadata formats are written into each comic every time
                  its tags are edited. Learn more about
                  <a
                    href="https://anansi-project.github.io/docs/category/comicinfo"
                    target="_blank"
                    >ComicInfo<v-icon size="small">{{
                      mdiOpenInNew
                    }}</v-icon></a
                  >
                  and
                  <a
                    href="https://metron-project.github.io/docs/category/metroninfo"
                    target="_blank"
                    >MetronInfo<v-icon size="small">{{
                      mdiOpenInNew
                    }}</v-icon></a
                  >.
                </template>
                <template v-else>{{ message }}</template>
              </template>
            </v-checkbox-group>
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
          <div class="adminCard">
            <v-checkbox
              v-model="draft.renameFiles"
              label="Rename files to the comicbox scheme"
              :hint="renameFilesHint"
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
              v-model="draft.defaultEffort"
              :items="effortChoices"
              label="Effort"
              :hint="effortHint"
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
      </v-form>

      <AdminSection title="Online Tagging Sources">
        <p class="adminHint sourcesHint">
          {{ sourcesOrderHint }}
        </p>
        <div class="sourcesGroup">
          <div
            v-for="source in sources"
            :key="source.id"
            class="sourceRow"
            :style="sourceRowStyle(source.id)"
          >
            <div
              class="sourceEnable"
              :title="isConfigured(source.id) ? '' : sourceDisabledTooltip"
            >
              <v-checkbox
                :model-value="isSourceEnabled(source.id)"
                :disabled="!isConfigured(source.id)"
                :aria-label="source.enableLabel"
                hide-details
                density="compact"
                @update:model-value="setSourceEnabled(source.id, $event)"
              />
              <div v-if="isSourceEnabled(source.id)" class="sourceOrderButtons">
                <v-btn
                  icon
                  variant="text"
                  density="compact"
                  :aria-label="source.raiseLabel"
                  :disabled="sourcePriority(source.id) <= 0"
                  @click="moveSource(source.id, -1)"
                >
                  <v-icon>{{ mdiChevronUp }}</v-icon>
                </v-btn>
                <v-btn
                  icon
                  variant="text"
                  density="compact"
                  :aria-label="source.lowerLabel"
                  :disabled="
                    sourcePriority(source.id) >=
                    (draft.defaultSources || []).length - 1
                  "
                  @click="moveSource(source.id, 1)"
                >
                  <v-icon>{{ mdiChevronDown }}</v-icon>
                </v-btn>
              </div>
            </div>
            <div class="sourcePanel">
              <v-expansion-panels
                :model-value="isConfigured(source.id) ? [] : [0]"
                variant="accordion"
              >
                <v-expansion-panel>
                  <v-expansion-panel-title>
                    <span class="adminCardTitle">{{ source.label }}</span>
                    <span
                      class="adminCardDesc credentialStatus"
                      :class="{
                        credentialSet: isConfigured(source.id),
                      }"
                    >
                      {{
                        isConfigured(source.id)
                          ? "API key set"
                          : "Not configured"
                      }}
                    </span>
                  </v-expansion-panel-title>
                  <v-expansion-panel-text>
                    <v-form class="adminFieldColumn" @submit.prevent>
                      <v-text-field
                        v-model="keys[source.id]"
                        label="API Key"
                        type="password"
                        autocomplete="new-password"
                        hide-details="auto"
                        density="compact"
                        :placeholder="
                          isConfigured(source.id)
                            ? 'New API Key'
                            : 'Enter API key'
                        "
                      />
                      <p class="adminHint">
                        {{ source.tokenHint }}
                        <a :href="source.tokenUrl" target="_blank"
                          >{{ source.tokenLinkText
                          }}<v-icon size="small">{{ mdiOpenInNew }}</v-icon></a
                        >
                      </p>
                      <v-text-field
                        v-if="source.customUrl"
                        v-model="urls[source.id]"
                        label="Custom URL (optional)"
                        autocomplete="off"
                        hide-details="auto"
                        density="compact"
                        :placeholder="defaults[source.fields.url] || 'Default'"
                      />
                      <div class="adminInlineActions">
                        <v-btn
                          variant="tonal"
                          size="small"
                          :disabled="!hasCredentialInput(source.id)"
                          @click="saveCredentials(source.id)"
                        >
                          {{ source.saveText }}
                        </v-btn>
                        <v-btn
                          variant="text"
                          size="small"
                          :loading="validating[source.id]"
                          :disabled="!canTest(source.id)"
                          @click="testCredentials(source.id)"
                        >
                          Test
                        </v-btn>
                        <ConfirmDialog
                          v-if="isConfigured(source.id)"
                          button-text="Clear API Key"
                          :title-text="source.clearTitle"
                          :text="source.clearText"
                          confirm-text="Clear"
                          variant="text"
                          size="small"
                          :block="false"
                          @confirm="clearCredentials(source.id)"
                        />
                      </div>
                      <ValidationChip
                        v-if="validationResult[source.id]"
                        :result="validationResult[source.id]"
                      />
                    </v-form>
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
import {
  isWriteFormatDisabled,
  KEEP_FORMAT_HINT,
  namedFormats,
  WRITE_FORMAT_CHOICES,
} from "@/components/metadata/edit-mode/write-formats";
import {
  credentialFields,
  SOURCE_DESCRIPTORS,
  SUPPORTED_SOURCES,
} from "@/components/online-tag/source-labels";
import { useAdminStore } from "@/stores/admin";

const EDITABLE_FIELDS = Object.freeze([
  "defaultFormats",
  "deleteOriginal",
  "renameFiles",
  "defaultMatchMode",
  "defaultPromptsMode",
  "defaultEffort",
  "defaultSources",
  "mergeAllSources",
]);

// One row per source, with the copy its credential panel shows.
const SOURCE_ROWS = Object.freeze(
  SUPPORTED_SOURCES.map((id) => {
    const descriptor = SOURCE_DESCRIPTORS[id];
    const { label, customUrl } = descriptor;
    return Object.freeze({
      id,
      ...descriptor,
      fields: credentialFields(id),
      enableLabel: `Enable ${label}`,
      raiseLabel: `Raise ${label} priority`,
      lowerLabel: `Lower ${label} priority`,
      saveText: customUrl
        ? `Save ${label} Credentials`
        : `Save ${label} API Key`,
      clearTitle: `Clear ${label} API Key`,
      clearText: customUrl
        ? `Remove the saved ${label} API key and custom URL?`
        : `Remove the saved ${label} API key?`,
    });
  }),
);

/** A fresh per-source state map, every source set to ``value``. */
function bySource(value) {
  return Object.fromEntries(SUPPORTED_SOURCES.map((id) => [id, value]));
}

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
      formatChoices: WRITE_FORMAT_CHOICES,
      matchModeChoices: TAGGING_CHOICES.matchMode,
      promptsModeChoices: TAGGING_CHOICES.promptsMode,
      effortChoices: TAGGING_CHOICES.effort,
      metadataFormatsHint:
        "These metadata formats are written into each comic every time its tags are edited. Learn more about ComicInfo and MetronInfo.",
      lastFormatHint: "At least one format must be written",
      keepFormatHint: KEEP_FORMAT_HINT,
      deleteOriginalHint:
        "Writing tags to CBR, CB7, or CBT archives converts them to CBZ. Enable this to delete the original file after conversion.",
      renameFilesHint:
        "Rename each comic file to the comicbox scheme derived from its tags after writing. Can be overridden per operation when editing tags or tagging online.",
      matchModeHint:
        "How aggressively to accept online matches. Ask writes nothing and prompts for every match, listing a clear Metron cover match first. Careful writes only near-certain matches and clear Metron cover matches, Auto also writes confident ones, and Eager also writes weaker best guesses.",
      effortHint:
        "How many Comic Vine requests a comic may spend searching. Thorough finds the most and costs the most against the hourly limit; Metron ignores this.",
      promptsModeHint:
        "What to do with matches that are too ambiguous to auto-write. Ask saves them as prompts to resolve later; Never skips them, writing only auto-matched comics.",
      sourceDisabledTooltip:
        "A source can only be enabled once its API key is saved.",
      sourcesOrderHint:
        "Enabled sources run in priority order — use the arrows to reorder. With Merge all sources off, the highest-priority source that finds a match tags the comic and the rest are skipped. With it on, every enabled source is queried for each comic and their results are merged into one record for the most complete metadata.",
      mergeAllSourcesHint:
        "Merging queries every enabled source for each comic instead of stopping at the first match, so it roughly multiplies online API calls by the number of enabled sources — scans take longer and hit rate limits sooner. Can be overridden per scan in the Tag Online dialog.",
      sources: SOURCE_ROWS,
      draft: pickFields(undefined),
      saving: false,
      pendingSave: false,
      // Typed, unsaved credentials, keyed by source.
      keys: bySource(""),
      urls: bySource(""),
      validating: bySource(false),
      validationResult: bySource(undefined),
    };
  },
  computed: {
    ...mapState(useAdminStore, {
      defaults: (state) => state.taggingDefaults,
    }),
    configuredSources() {
      // The sources with a stored API key, as the server reports them.
      return new Set(this.defaults?.configuredSources || []);
    },
    formatsMessages() {
      // The last checked format's box is disabled; say why under the hints.
      const messages = [this.metadataFormatsHint, this.keepFormatHint];
      if (namedFormats(this.draft.defaultFormats).length === 1) {
        messages.push(this.lastFormatHint);
      }
      return messages;
    },
    formatsError() {
      // Only a row saved empty before formats were required gets here. Don't
      // fill in a default, which would auto-save on open; checking a box does.
      return namedFormats(this.draft.defaultFormats).length
        ? []
        : ["Choose at least one format"];
    },
    canMerge() {
      // Merging needs at least two enabled sources; with one there's nothing
      // to merge. isSourceEnabled already gates on credentials.
      return (
        SUPPORTED_SOURCES.filter((source) => this.isSourceEnabled(source))
          .length >= 2
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
    isFormatDisabled(value) {
      return isWriteFormatDisabled(this.draft.defaultFormats, value);
    },
    isConfigured(source) {
      return this.configuredSources.has(source);
    },
    isSourceEnabled(source) {
      // The enable checkboxes drive ``draft.defaultSources``, which auto-saves
      // with the rest of the defaults. A source can only be checked once its
      // credentials exist, so gate on the stored credentials too — a
      // credential-less source always reads as off-and-disabled.
      return (
        this.isConfigured(source) &&
        (this.draft.defaultSources || []).includes(source)
      );
    },
    canTest(source) {
      return Boolean(this.keys[source]) || this.isConfigured(source);
    },
    credentialInput(source) {
      // The typed fields, under the names the API takes them by.
      const { key, url } = credentialFields(source);
      const data = {};
      if (this.keys[source]) data[key] = this.keys[source];
      if (url && this.urls[source]) data[url] = this.urls[source];
      return data;
    },
    hasCredentialInput(source) {
      return Object.keys(this.credentialInput(source)).length > 0;
    },
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
    async saveCredentials(source) {
      const data = this.credentialInput(source);
      this.validationResult[source] = undefined;
      const hadCredentials = this.isConfigured(source);
      await this.updateTaggingDefaults(data);
      this.keys[source] = "";
      this.urls[source] = "";
      // Configuring a brand-new source enables it automatically; re-saving
      // credentials respects the existing checkbox state.
      if (!hadCredentials && this.isConfigured(source)) {
        this.setSourceEnabled(source, true);
      }
    },
    clearCredentials(source) {
      // Clearing the key clears a custom url with it.
      const { key, url } = credentialFields(source);
      const data = { [key]: "" };
      if (url) data[url] = "";
      this.validationResult[source] = undefined;
      this.updateTaggingDefaults(data);
    },
    async testCredentials(source) {
      const payload = { source, ...this.credentialInput(source) };
      await this._runValidation(source, payload);
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

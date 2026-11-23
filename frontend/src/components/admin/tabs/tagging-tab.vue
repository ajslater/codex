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
        <div class="sourcesMode">
          <v-btn-toggle
            v-model="draft.mergeAllSources"
            aria-label="How the enabled sources combine"
            color="primary"
            density="compact"
            variant="outlined"
            divided
            mandatory
          >
            <v-btn :value="false">First match</v-btn>
            <v-btn :value="true" :disabled="!canMerge">Merge all sources</v-btn>
          </v-btn-toggle>
          <p class="adminHint sourcesModeHint">
            {{ canMerge ? mergeAllSourcesHint : mergeDisabledHint }}
          </p>
        </div>
        <p class="d-sr-only sourceMoveAnnouncement" aria-live="polite">
          {{ moveAnnouncement }}
        </p>
        <div ref="sourcesGroup" class="sourcesGroup">
          <div
            v-for="source in sources"
            :key="source.id"
            class="sourceRow"
            :class="{ sourceRowDragging: dragSource === source.id }"
            :data-source="source.id"
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
            </div>
            <button
              v-if="isSourceEnabled(source.id)"
              type="button"
              class="sourceHandle"
              :aria-label="source.moveLabel"
              :title="moveTooltip"
              @pointerdown="startDrag($event, source.id)"
              @pointermove="dragTo"
              @pointerup="endDrag"
              @pointercancel="cancelDrag"
              @lostpointercapture="cancelDrag"
              @keydown="onHandleKey($event, source.id)"
            >
              <v-icon>{{ mdiDragVertical }}</v-icon>
            </button>
            <span v-else class="sourceHandle" aria-hidden="true" />
            <div class="sourcePanel">
              <v-expansion-panels
                :model-value="isConfigured(source.id) ? [] : [0]"
                variant="accordion"
              >
                <v-expansion-panel>
                  <v-expansion-panel-title class="sourceTitle">
                    <span v-if="sourceRank(source.id)" class="sourceRank">
                      {{ sourceRank(source.id) }}
                    </span>
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
                    <span v-if="sourceRole(source.id)" class="sourceRoleSlot">
                      <span
                        class="sourceRole"
                        :class="{ sourceRoleLead: sourceRank(source.id) === 1 }"
                      >
                        {{ sourceRole(source.id) }}
                      </span>
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
                      <p v-if="source.notes" class="adminHint sourceNotes">
                        {{ source.notes }}
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
      </AdminSection>
      <TagWriteErrorsPanel />
    </template>
  </div>
</template>

<script>
import { mdiDragVertical, mdiOpenInNew } from "@mdi/js";
import { dequal } from "dequal";
import { mapActions, mapState } from "pinia";

import TAGGING_CHOICES from "@/choices/tagging-choices.json";
import TAGGING_ESTIMATE from "@/choices/tagging-estimate.json";
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
import { NUMBER_FORMAT } from "@/datetime";
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

/*
 * A source whose daily cap binds every account gets its budget spelled out:
 * the free tier's hourly and daily caps and what one comic costs, all as
 * comicbox prices them (tagging-estimate.json).
 */
function budgetNote(id) {
  const rate = TAGGING_ESTIMATE.sourceRates[id];
  const perComic = TAGGING_ESTIMATE.requestsPerComic[id]?.balanced;
  if (!rate?.perDay || !perComic) return "";
  const perHour = NUMBER_FORMAT.format(rate.perHour);
  const perDay = NUMBER_FORMAT.format(rate.perDay);
  return `Free tier: ${perHour} requests an hour and ${perDay} a day, about ${perComic} per comic.`;
}

// The keys that move a focused drag handle, and which way.
const MOVE_KEYS = Object.freeze({ ArrowUp: -1, ArrowDown: 1 });

// What each enabled source does in a scan, by mode and rank.
const SOURCE_ROLES = Object.freeze({
  only: "Only source",
  firstMatch: Object.freeze({ lead: "Tried first", rest: "If no match" }),
  merge: Object.freeze({ lead: "Wins conflicts", rest: "Fills gaps" }),
});

// One row per source, with the copy its credential panel shows.
const SOURCE_ROWS = Object.freeze(
  SUPPORTED_SOURCES.map((id) => {
    const descriptor = SOURCE_DESCRIPTORS[id];
    const { label, customUrl } = descriptor;
    return Object.freeze({
      id,
      ...descriptor,
      fields: credentialFields(id),
      notes: [budgetNote(id), descriptor.terms].filter(Boolean).join(" "),
      enableLabel: `Enable ${label}`,
      moveLabel: `Reorder ${label}: drag, or press the up and down arrow keys`,
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
      mdiDragVertical,
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
        "How many Comic Vine requests a comic may spend searching. Thorough finds the most and costs the most against the hourly limit; Metron and VerseDB ignore this.",
      promptsModeHint:
        "What to do with matches that are too ambiguous to auto-write. Ask saves them as prompts to resolve later; Never skips them, writing only auto-matched comics.",
      sourceDisabledTooltip:
        "A source can only be enabled once its API key is saved.",
      sourcesOrderHint:
        "The enabled sources below are listed in priority order, highest first; drag one by its handle to reorder them. With First match, the first source in the list that finds a match tags the comic and the rest are skipped. With Merge all sources, every enabled source is queried and their results are merged into one record; where they disagree, the source higher in the list wins.",
      mergeAllSourcesHint:
        "Merging queries every enabled source for each comic instead of stopping at the first match, so it roughly multiplies online API calls by the number of enabled sources — scans take longer and hit rate limits sooner. Can be overridden per scan in the Tag Online dialog.",
      mergeDisabledHint:
        "Merging needs two or more enabled sources: enable another one below.",
      sources: SOURCE_ROWS,
      moveTooltip: "Drag to reorder",
      // The source being dragged, and the order the drag would save; null
      // when nothing is being dragged.
      dragSource: "",
      dragOrder: null,
      // Read out by screen readers after each move.
      moveAnnouncement: "",
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
    activeSources() {
      // The enabled sources in priority order: what a scan runs.
      // isSourceEnabled already gates on credentials, so a source that
      // lingers in defaultSources without them is left out.
      return (this.draft.defaultSources || []).filter((source) =>
        this.isSourceEnabled(source),
      );
    },
    shownSources() {
      // The order on screen: a drag in progress previews its own, unsaved.
      return this.dragOrder || this.activeSources;
    },
    canMerge() {
      // Merging needs at least two enabled sources; with one there's nothing
      // to merge.
      return this.activeSources.length >= 2;
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
      // defaultSources order is priority: run order, and with Merge all
      // sources on, who wins where sources disagree. A newly enabled
      // source joins at the end (lowest priority).
      const sources = (this.draft.defaultSources || []).filter(
        (s) => s !== source,
      );
      if (enabled) {
        sources.push(source);
      }
      this.draft.defaultSources = sources;
    },
    sourceRowStyle(source) {
      // Render rows in priority order via flex order; sources that aren't
      // enabled sink below the enabled ones, so those stay contiguous.
      const index = this.shownSources.indexOf(source);
      return { order: index === -1 ? 99 : index };
    },
    sourceRank(source) {
      // 1 for the highest-priority enabled source; 0 for one not enabled.
      return this.shownSources.indexOf(source) + 1;
    },
    sourceRole(source) {
      // What this source does in a scan, as its row's tag says.
      const rank = this.sourceRank(source);
      if (!rank) {
        return "";
      }
      if (this.shownSources.length === 1) {
        return SOURCE_ROLES.only;
      }
      const roles = this.draft.mergeAllSources
        ? SOURCE_ROLES.merge
        : SOURCE_ROLES.firstMatch;
      return rank === 1 ? roles.lead : roles.rest;
    },
    saveOrder(order, moved) {
      // Store a new order of the enabled sources. defaultSources may still
      // list a source that lost its credentials; it keeps its place after
      // them, where it neither runs nor shows a rank.
      if (dequal(order, this.activeSources)) {
        return;
      }
      const rest = (this.draft.defaultSources || []).filter(
        (source) => !order.includes(source),
      );
      this.draft.defaultSources = [...order, ...rest];
      const { label } = SOURCE_ROWS.find((row) => row.id === moved);
      const rank = order.indexOf(moved) + 1;
      this.moveAnnouncement = `${label} moved to ${rank} of ${order.length}.`;
    },
    moveSource(source, delta) {
      // Swap a source with its enabled neighbour, as the arrow keys do.
      const order = [...this.activeSources];
      const from = order.indexOf(source);
      const to = from + delta;
      if (from === -1 || to < 0 || to >= order.length) {
        return;
      }
      [order[from], order[to]] = [order[to], order[from]];
      this.saveOrder(order, source);
    },
    onHandleKey(event, source) {
      if (event.key === "Escape") {
        this.cancelDrag();
        return;
      }
      const delta = MOVE_KEYS[event.key];
      if (!delta || this.dragSource) {
        return;
      }
      // Keep the page from scrolling.
      event.preventDefault();
      this.moveSource(source, delta);
    },
    startDrag(event, source) {
      if (event.button !== 0) {
        return;
      }
      // No text selection while dragging.
      event.preventDefault();
      this.dragSource = source;
      this.dragOrder = [...this.activeSources];
      const handle = event.currentTarget;
      // Focused so Escape can drop the drag, without a keyboard focus ring.
      handle.focus({ focusVisible: false });
      try {
        // Every later pointer event comes to this handle, wherever the
        // pointer goes.
        handle.setPointerCapture(event.pointerId);
      } catch {
        // Not a pointer that is down (a synthetic event): the drag still
        // follows it while it stays over the handle.
      }
    },
    rowMiddle(source) {
      const row = this.$refs.sourcesGroup?.querySelector(
        `[data-source="${source}"]`,
      );
      const box = row?.getBoundingClientRect();
      return box ? box.top + box.height / 2 : 0;
    },
    dragTo(event) {
      // Put the dragged source after every other row whose middle is above
      // the pointer. The rows move as the order changes, so this settles
      // instead of flickering between two places.
      if (!this.dragSource) {
        return;
      }
      const others = this.dragOrder.filter(
        (source) => source !== this.dragSource,
      );
      const above = others.filter(
        (source) => this.rowMiddle(source) < event.clientY,
      ).length;
      const order = [...others];
      order.splice(above, 0, this.dragSource);
      if (!dequal(order, this.dragOrder)) {
        this.dragOrder = order;
      }
    },
    endDrag() {
      const { dragSource, dragOrder } = this;
      this.cancelDrag();
      if (dragOrder) {
        this.saveOrder(dragOrder, dragSource);
      }
    },
    cancelDrag() {
      this.dragSource = "";
      this.dragOrder = null;
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
@use "sass:map";
@use "vuetify/styles/settings/variables" as vuetify;
@use "@/components/admin/tabs/admin-section.scss";
@use "@/components/admin/tabs/design.scss" as d;

$rank-size: 20px;

// The name and key status never break mid-phrase; on a phone the role tag
// moves to a line of its own instead.
.sourceTitle .adminCardTitle {
  white-space: nowrap;
}

// Grows to take the title's free space, which puts the role tag after it
// right against the chevron.
.credentialStatus {
  flex: 1 1 auto;
  margin-left: d.$space-2;
  white-space: nowrap;
}

// The source's priority, before its name. Only enabled sources have one.
.sourceRank {
  flex: none;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: $rank-size;
  height: $rank-size;
  margin-right: d.$space-2;
  border-radius: 50%;
  font-size: d.$text-meta;
  background-color: rgba(var(--v-theme-on-surface), 0.12);
}

// What the source does in a scan, just before the panel's chevron.
.sourceRoleSlot {
  flex: none;
  margin: 0 d.$space-2;
}

.sourceRole {
  display: inline-block;
  padding: 2px d.$space-2;
  border-radius: d.$radius-sm;
  font-size: d.$text-small;
  color: rgb(var(--v-theme-text-secondary));
  white-space: nowrap;
}

.sourceRoleLead {
  color: rgb(var(--v-theme-primary));
  background-color: rgba(var(--v-theme-primary), 0.16);
}

// A phone has no room for the tag beside the name: it takes the next line,
// under the name, and the chevron stays on the first.
@media #{map.get(vuetify.$display-breakpoints, 'xs')} {
  .sourceTitle {
    flex-wrap: wrap;
    row-gap: d.$space-1;
  }

  .sourceRoleSlot {
    order: 1;
    flex-basis: 100%;
    margin: 0 0 0 calc(#{$rank-size} + #{d.$space-2});
  }
}

.credentialSet {
  color: rgb(var(--v-theme-success));
}

.sourcesHint {
  margin-top: d.$space-2;
}

// How the enabled sources combine, right above the list it changes.
.sourcesMode {
  margin-top: d.$space-3;
}

.sourcesModeHint {
  margin-top: d.$space-1;
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

// The grip that reorders a source, between its checkbox and its panel. A
// source that isn't enabled keeps an empty one, so every panel lines up.
.sourceHandle {
  flex: none;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 24px;
  height: 32px;
  margin-top: d.$space-2;
  padding: 0;
  border: none;
  border-radius: d.$radius-sm;
  background: none;
  color: rgb(var(--v-theme-text-secondary));
  cursor: grab;
  // A touch on the grip drags the source instead of scrolling the page.
  touch-action: none;
}

button.sourceHandle:hover,
button.sourceHandle:focus-visible {
  color: rgb(var(--v-theme-on-surface));
  background-color: rgba(var(--v-theme-on-surface), 0.08);
}

button.sourceHandle:focus-visible {
  outline: 2px solid rgb(var(--v-theme-primary));
}

// The source being dragged stands out, and the grip says it's held.
.sourceRowDragging .sourcePanel {
  border-radius: d.$radius;
  box-shadow: 0 0 0 2px rgb(var(--v-theme-primary));
}

.sourceRowDragging .sourceHandle {
  cursor: grabbing;
  color: rgb(var(--v-theme-primary));
}

.sourcePanel {
  flex: 1 1 auto;
  min-width: 0;
}

.sourceNotes {
  margin-top: 0;
}
</style>

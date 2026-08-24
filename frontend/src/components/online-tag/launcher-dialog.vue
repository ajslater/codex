<template>
  <v-dialog v-model="dialog" max-width="500">
    <template #activator="{ props: activatorProps }">
      <v-btn v-bind="activatorProps" variant="tonal" :size="size">
        Tag Online
      </v-btn>
    </template>
    <v-card>
      <v-card-title>Online Tagging</v-card-title>
      <v-card-text>
        <div v-if="allSourcesDisabled" class="credentialWarning">
          No online source API keys configured.
          <router-link :to="{ name: 'admin-tagging' }">
            Configure in Admin &rarr; Tagging
          </router-link>
        </div>
        <template v-else>
          <div v-if="metronLegacyCredentials" class="credentialWarning">
            Metron password authentication is deprecated.
            <router-link :to="{ name: 'admin-tagging' }">
              Add an API key in Admin &rarr; Tagging
            </router-link>
          </div>
          <v-select
            v-model="sources"
            :items="sourceItems"
            label="Sources"
            multiple
            chips
            hide-details
            density="compact"
            class="mt-4"
          />
          <template v-if="idTaggable">
            <div v-if="existingOptions.length" class="existingIds mt-3">
              <span class="existingIdsLabel">This comic's IDs:</span>
              <v-chip
                v-for="opt in existingOptions"
                :key="opt.value"
                class="existingIdChip"
                size="small"
                variant="outlined"
                @click="addId(opt.value)"
              >
                {{ opt.title }}
              </v-chip>
            </div>
            <v-combobox
              :model-value="idInputs"
              label="Issue URLs or IDs"
              placeholder="metron:ID, comicvine:ID, or issue URL"
              :hint="idInputsHint"
              persistent-hint
              multiple
              chips
              closable-chips
              density="compact"
              class="mt-3"
              @update:model-value="setIdInputs"
            />
            <v-select
              v-if="needsSourceSelect"
              v-model="sourceChoice"
              :items="sourceChoices"
              label="Source"
              hint="That id is just a number — choose which source it belongs to."
              persistent-hint
              density="compact"
              class="mt-3"
            />
            <div v-if="needsSourcePick" class="pickSourceWarning">
              Bare ID &mdash; choose Metron or Comic Vine.
            </div>
            <div v-if="unconfiguredIdWarning" class="pickSourceWarning">
              {{ unconfiguredIdWarning }}
            </div>
            <div v-if="duplicateIdWarning" class="pickSourceWarning">
              {{ duplicateIdWarning }}
            </div>
          </template>
          <v-checkbox
            v-if="bothConfigured"
            v-model="mergeAllSources"
            label="Merge all sources"
            :hint="mergeAllSourcesHint"
            :disabled="!canMerge || searchControlsDisabled"
            persistent-hint
            density="compact"
            class="mt-3"
          />
          <v-select
            v-model="matchMode"
            :items="matchModeChoices"
            label="Match Mode"
            :hint="matchModeHint"
            :disabled="searchControlsDisabled"
            persistent-hint
            density="compact"
            class="mt-3"
          />
          <v-select
            v-model="promptsMode"
            :items="promptsModeChoices"
            label="Prompts"
            :hint="promptsModeHint"
            :disabled="searchControlsDisabled"
            persistent-hint
            density="compact"
            class="mt-3"
          />
          <v-checkbox
            v-model="rename"
            label="Rename files to comicbox scheme"
            :hint="renameHint"
            persistent-hint
            density="compact"
            class="mt-3"
          />
          <div class="tagInfo">
            <div class="comicCount">
              {{ comicCount }} comic{{ comicCount === 1 ? "" : "s" }} to look up
            </div>
            <div v-if="rateLimitWarning" class="rateLimitWarning">
              {{ rateLimitWarning }}
            </div>
            <div class="timeEstimate">Estimated time: {{ timeEstimate }}</div>
            <div v-if="needConversion > 0" class="conversionWarning">
              <div>
                {{ needConversion }}
                comic{{ needConversion === 1 ? "" : "s" }} will be converted to
                CBZ.
              </div>
              <div class="conversionHelpText">
                Writing tags to CBR, CB7, or CBT archives converts them to CBZ.
                Enable this to delete the original file after conversion.
              </div>
              <v-checkbox
                v-model="deleteOriginal"
                label="Delete original files after conversion"
                hide-details
                density="compact"
                class="mt-2"
              />
            </div>
          </div>
        </template>
      </v-card-text>
      <v-card-actions>
        <v-spacer />
        <v-btn variant="text" @click="dialog = false">Cancel</v-btn>
        <v-btn
          color="primary"
          variant="flat"
          :loading="working"
          :disabled="actionDisabled"
          @click="submit"
        >
          {{ actionLabel }}
        </v-btn>
      </v-card-actions>
    </v-card>
  </v-dialog>
</template>

<script>
import { mapActions, mapState } from "pinia";

import { HTTP } from "@/api/v4/base";
import TAGGING_CHOICES from "@/choices/tagging-choices.json";
import TAGGING_ESTIMATE from "@/choices/tagging-estimate.json";
import { sourceLabel } from "@/components/online-tag/source-labels";
import { useAdminStore } from "@/stores/admin";
import { useCommonStore } from "@/stores/common";
import { useOnlineTagStore } from "@/stores/online-tag";

// Base match-mode semantics, shown for any source. The per-comic request
// count is Comic Vine-specific (Metron is a flat two-step regardless of mode),
// so it's appended by matchModeHint only when Comic Vine is an active source.
const MATCH_MODE_HINTS = {
  careful:
    "Only accepts high-confidence, unambiguous matches. Defers anything uncertain for manual review.",
  auto: "Balances accuracy and speed. Accepts confident matches automatically and defers uncertain ones.",
  eager:
    "Accepts the best available match with minimal verification. Fastest, but least precise.",
};
const PROMPTS_MODE_HINTS = {
  ask: "Pauses on ambiguous matches and asks you to choose the correct result.",
  never:
    "Skips all ambiguous matches without prompting. Unmatched comics are left unchanged.",
};

// Display names are UI copy (see source-labels); the per-source rates and
// per-comic request model derive from comicbox via tagging-estimate.json
// (build-choices), so the client estimate tracks the backend instead of
// hand-syncing constants.
const SOURCE_RATES = Object.fromEntries(
  Object.entries(TAGGING_ESTIMATE.sourceRates).map(([source, rate]) => [
    source,
    { ...rate, label: sourceLabel(source) },
  ]),
);

function callsForSource(source, mode) {
  if (source === "metron") return TAGGING_ESTIMATE.metronRequestsPerComic;
  if (source === "comicvine") {
    return (
      TAGGING_ESTIMATE.comicvineRequestsByMode[mode] ||
      TAGGING_ESTIMATE.defaultRequestsPerComic
    );
  }
  return TAGGING_ESTIMATE.defaultRequestsPerComic;
}

// Only these sources support online id tagging; derived from comicbox's
// SOURCE_NAMES via the tagging choices so it tracks the backend. Other
// identifiers a comic carries aren't offered.
const TAGGABLE_SOURCES = Object.freeze(new Set(TAGGING_CHOICES.sources));
// A comic's own issue identifier is stored with id_type "comic" — codex's
// IdentifierType.ISSUE value is the table name, not "issue". Accept that (and
// a bare "issue" defensively); skip non-issue types like publisher / series.
const ISSUE_TYPES = Object.freeze(new Set(["comic", "issue"]));

function formatDuration(minutes) {
  if (minutes < 1) return "under a minute";
  if (minutes < 60) {
    const m = Math.ceil(minutes);
    return `~${m} minute${m === 1 ? "" : "s"}`;
  }
  const h = Math.floor(minutes / 60);
  const m = Math.ceil(minutes % 60);
  if (m === 0) return `~${h} hour${h === 1 ? "" : "s"}`;
  return `~${h}h ${m}m`;
}

export default {
  name: "OnlineTagLauncherDialog",
  props: {
    book: {
      type: Object,
      required: true,
    },
    identifiers: {
      type: Array,
      default: () => [],
    },
    size: {
      type: String,
      default: "default",
    },
  },
  emits: ["started"],
  data() {
    return {
      dialog: false,
      working: false,
      matchModeChoices: TAGGING_CHOICES.matchMode,
      promptsModeChoices: TAGGING_CHOICES.promptsMode,
      sources: [...TAGGING_CHOICES.sources],
      matchMode: "auto",
      promptsMode: "ask",
      mergeAllSources: false,
      mergeAllSourcesBaseHint:
        "Off: the highest-priority selected source that matches tags the comic and the rest are skipped. On: every selected source is queried and their results are merged for the most complete tags — but that roughly multiplies API calls by the number of sources, so it's slower and rate-limited sooner.",
      // A pinned source is always fetched, first-wins or not, so with every
      // selected source pinned their results merge no matter the setting.
      allPinnedMergeHint:
        "Always on when every selected source is tagged by ID — each pinned id is fetched and merged.",
      needConversion: 0,
      deleteOriginal: false,
      rename: false,
      renameHint:
        "Rename each tagged comic file to the comicbox scheme derived from its new tags.",
      pinnedControlsHint: "Not used when all sources are tagged by ID.",
      idInputsHint:
        "Enter one or more issue URLs or ids (metron:ID, comicvine:ID, 4000-ID). A source with an id is fetched directly; the rest are searched.",
      // Pinned ids
      idInputs: [],
      sourceChoice: "auto",
    };
  },
  computed: {
    ...mapState(useAdminStore, ["taggingDefaults"]),
    orderedSelectedSources() {
      // Checkbox v-model arrays append in click order; submit in the
      // admin-configured priority order instead, since source order is
      // run priority (first match wins). Unlisted sources keep their
      // relative selection order after the listed ones.
      const priority = this.taggingDefaults?.defaultSources || [];
      const rank = (s) => {
        const index = priority.indexOf(s);
        return index === -1 ? priority.length : index;
      };
      return [...this.sources].sort((a, b) => rank(a) - rank(b));
    },
    hasMetron() {
      return Boolean(this.taggingDefaults?.hasMetronCredentials);
    },
    hasComicvine() {
      return Boolean(this.taggingDefaults?.hasComicvineCredentials);
    },
    // Metron still authenticates with a legacy username & password, which
    // metron.cloud is retiring in favor of API keys. Only worth saying when
    // this session would actually query Metron.
    metronLegacyCredentials() {
      return (
        this.hasMetron &&
        !this.taggingDefaults?.metronKeySet &&
        this.metronSessionEnabled
      );
    },
    metronSessionEnabled() {
      // Pinning an id selects its source, so the selection is the whole story.
      return this.activeSources.includes("metron");
    },
    bothConfigured() {
      return this.hasMetron && this.hasComicvine;
    },
    sourceItems() {
      return [
        {
          title: "Metron Cloud",
          value: "metron",
          props: this.hasMetron ? {} : { disabled: true },
        },
        {
          title: "Comic Vine",
          value: "comicvine",
          props: this.hasComicvine ? {} : { disabled: true },
        },
      ];
    },
    allSourcesDisabled() {
      return !this.hasMetron && !this.hasComicvine;
    },
    enabledSources() {
      // The sources that could run at all: credentials configured.
      return new Set(
        this.sourceItems.filter((s) => !s.props?.disabled).map((s) => s.value),
      );
    },
    idTaggable() {
      // Pinning an id is per-issue: only when the selection is exactly one
      // comic. Search still works for any number of them.
      return (
        this.book?.collection === "comics" &&
        (this.book?.ids?.length ?? 0) === 1
      );
    },
    // --- pinned ids -----------------------------------------------------
    existingOptions() {
      // Offer the comic's own Metron / Comic Vine issue identifiers as
      // one-click fills (``source:code``) so the operator can re-tag from a
      // known id without retyping it.
      const seen = new Set();
      const options = [];
      for (const row of this.identifiers) {
        if (!TAGGABLE_SOURCES.has(row.source) || !row.code) {
          continue;
        }
        if (row.type && !ISSUE_TYPES.has(row.type)) {
          continue;
        }
        const value = `${row.source}:${row.code}`;
        if (seen.has(value)) {
          continue;
        }
        seen.add(value);
        options.push({
          value,
          title: `${row.displayName || row.source} ${row.code}`,
        });
      }
      return options;
    },
    sourceChoices() {
      const choices = [{ title: "Auto-detect", value: "auto" }];
      if (this.hasMetron) {
        choices.push({ title: "Metron", value: "metron" });
      }
      if (this.hasComicvine) {
        choices.push({ title: "Comic Vine", value: "comicvine" });
      }
      return choices;
    },
    idTokens() {
      // Each chip is one identifier; trim and drop blanks.
      return this.idInputs.map((s) => String(s).trim()).filter(Boolean);
    },
    needsSourceSelect() {
      // Only a bare number (or otherwise unrecognizable token) needs a manual
      // source — URLs, metron:/comicvine: prefixes, and 4000- ids self-identify.
      // A lone configured source resolves a bare number on its own.
      return (
        this.bothConfigured &&
        this.idTokens.some((t) => this.detectSource(t) === null)
      );
    },
    needsSourcePick() {
      return this.needsSourceSelect && this.sourceChoice === "auto";
    },
    soleConfiguredSource() {
      if (this.bothConfigured) return null;
      if (this.hasMetron) return "metron";
      return this.hasComicvine ? "comicvine" : null;
    },
    tokensBySource() {
      // Group the entered tokens by the source each resolves to. A token whose
      // source is still unknown (a bare number with nothing to disambiguate it)
      // is left out; needsSourcePick surfaces that instead.
      const bySource = {};
      if (!this.idTaggable) return bySource;
      for (const token of this.idTokens) {
        const source = this.resolveTokenSource(token);
        if (source) {
          (bySource[source] ||= []).push(token);
        }
      }
      return bySource;
    },
    pinnedIds() {
      // One id per source — the first entered wins, which is also all the
      // server can keep since the payload is a per-source mapping.
      const ids = {};
      for (const [source, tokens] of Object.entries(this.tokensBySource)) {
        if (this.enabledSources.has(source)) {
          ids[source] = tokens[0];
        }
      }
      return ids;
    },
    pinnedSources() {
      return Object.keys(this.pinnedIds);
    },
    anySelectedPinned() {
      return this.activeSources.some((s) => s in this.pinnedIds);
    },
    allSelectedPinned() {
      return (
        this.activeSources.length > 0 &&
        this.activeSources.every((s) => s in this.pinnedIds)
      );
    },
    searchControlsDisabled() {
      // A pinned id is unambiguous: nothing to match or prompt about.
      return this.allSelectedPinned;
    },
    unconfiguredIdTokens() {
      return Object.keys(this.tokensBySource).filter(
        (source) => !this.enabledSources.has(source),
      );
    },
    unconfiguredIdWarning() {
      const sources = this.unconfiguredIdTokens;
      if (sources.length === 0) return "";
      const names = sources.map((s) => sourceLabel(s)).join(", ");
      return `No ${names} credentials configured.`;
    },
    duplicateIdWarning() {
      const dupes = Object.entries(this.tokensBySource)
        .filter(([, tokens]) => tokens.length > 1)
        .map(([source]) => sourceLabel(source));
      if (dupes.length === 0) return "";
      return `More than one ${dupes.join(", ")} id — only the first is used.`;
    },
    // --- action button --------------------------------------------------
    actionLabel() {
      if (!this.anySelectedPinned) return "Search";
      return this.allSelectedPinned ? "Tag by ID" : "Tag by ID & Search";
    },
    searchDisabled() {
      return !this.sources.some((s) => this.enabledSources.has(s));
    },
    actionDisabled() {
      return Boolean(
        this.allSourcesDisabled ||
        this.searchDisabled ||
        this.needsSourcePick ||
        this.unconfiguredIdTokens.length,
      );
    },
    // --- search hints / estimates ---------------------------------------
    matchModeHint() {
      if (this.searchControlsDisabled) return this.pinnedControlsHint;
      const base = MATCH_MODE_HINTS[this.matchMode] || "";
      // The request-count tail only applies to Comic Vine, whose calls scale
      // with match mode; Metron's flat two-step doesn't, so skip it otherwise.
      if (!this.activeSources.includes("comicvine")) {
        return base;
      }
      const requests = TAGGING_ESTIMATE.comicvineRequestsByMode[this.matchMode];
      return requests
        ? `${base} ~${requests} Comic Vine requests/comic.`
        : base;
    },
    promptsModeHint() {
      if (this.searchControlsDisabled) return this.pinnedControlsHint;
      return PROMPTS_MODE_HINTS[this.promptsMode] || "";
    },
    comicCount() {
      return this.book.childCount || 1;
    },
    activeSources() {
      return this.sources.filter((s) => this.enabledSources.has(s));
    },
    canMerge() {
      // Nothing to merge with fewer than two sources selected.
      return this.activeSources.length >= 2;
    },
    mergeAllSourcesHint() {
      return this.searchControlsDisabled
        ? this.allPinnedMergeHint
        : this.mergeAllSourcesBaseHint;
    },
    totalCalls() {
      // Per-comic API calls are counted per source. Merge mode queries every
      // active source per comic (sum); first-match-wins stops at the first
      // source that answers, so bill the costliest single source. Keep this in
      // sync with estimate_seconds in codex/librarian/onlinetag/estimate.py.
      // A pinned source is one fetch, no search.
      const perSource = this.activeSources.map((s) =>
        s in this.pinnedIds ? 1 : callsForSource(s, this.matchMode),
      );
      if (perSource.length === 0) return 0;
      const callsPerComic = this.mergeAllSources
        ? perSource.reduce((sum, n) => sum + n, 0)
        : Math.max(...perSource);
      return this.comicCount * callsPerComic;
    },
    slowestRate() {
      let minRate = Infinity;
      for (const src of this.activeSources) {
        const rate = SOURCE_RATES[src];
        if (rate && rate.perMinute < minRate) {
          minRate = rate.perMinute;
        }
      }
      return minRate === Infinity ? 10 : minRate;
    },
    estimatedMinutes() {
      return this.totalCalls / this.slowestRate;
    },
    timeEstimate() {
      if (this.activeSources.length === 0) return "N/A";
      return formatDuration(this.estimatedMinutes);
    },
    rateLimitWarning() {
      if (this.activeSources.length === 0) return "";
      const warnings = [];
      for (const src of this.activeSources) {
        const rate = SOURCE_RATES[src];
        if (!rate) continue;
        if (this.totalCalls > rate.perHour) {
          warnings.push(`${rate.label} (${rate.perHour}/hr limit)`);
        } else if (this.totalCalls > rate.perMinute) {
          warnings.push(`${rate.label} (${rate.perMinute}/min limit)`);
        }
      }
      if (warnings.length === 0) return "";
      return `Will be rate-limited by: ${warnings.join(", ")}`;
    },
  },
  watch: {
    dialog(to) {
      if (to) {
        this.idInputs = [];
        this.sourceChoice = "auto";
        this.initFromDefaults();
      }
    },
    pinnedSources(to) {
      // Pinning an id for a source the operator hasn't selected would silently
      // do nothing (and the server rejects it), so selecting it is the only
      // sensible reading of entering the id.
      const missing = to.filter((s) => !this.sources.includes(s));
      if (missing.length) {
        this.sources = [...this.sources, ...missing];
      }
    },
  },
  methods: {
    ...mapActions(useAdminStore, ["loadTaggingDefaults"]),
    ...mapActions(useOnlineTagStore, ["startSession"]),
    resolveTokenSource(token) {
      // Self-identifying token first, then the manual pick, then the only
      // source there is. Null when it's still an ambiguous bare number.
      return (
        this.detectSource(token) ||
        (this.sourceChoice === "auto" ? null : this.sourceChoice) ||
        this.soleConfiguredSource
      );
    },
    detectSource(token) {
      // Cheap source detection mirroring the backend parser's self-identifying
      // forms; returns null when the token is just a number (ambiguous) or
      // otherwise unrecognizable, so the UI can ask which source it is.
      const t = String(token).trim().toLowerCase();
      if (!t) return null;
      if (t.includes("metron")) return "metron";
      if (t.includes("comicvine")) return "comicvine";
      if (/^4000-\d+$/.test(t)) return "comicvine";
      return null;
    },
    setIdInputs(value) {
      // Chips may arrive with embedded separators (paste / typed "a, b"); split
      // on whitespace and commas and dedupe so each chip is one identifier.
      const out = [];
      for (const item of value || []) {
        for (const part of String(item).split(/[\s,]+/)) {
          const token = part.trim();
          if (token && !out.includes(token)) {
            out.push(token);
          }
        }
      }
      this.idInputs = out;
    },
    addId(value) {
      if (!this.idInputs.includes(value)) {
        this.idInputs = [...this.idInputs, value];
      }
    },
    async initFromDefaults() {
      await this.loadTaggingDefaults();
      if (this.taggingDefaults) {
        const defaults = this.taggingDefaults.defaultSources || [];
        this.sources = defaults.filter((s) => this.enabledSources.has(s));
        this.matchMode =
          this.taggingDefaults.defaultMatchMode || this.matchMode;
        this.promptsMode =
          this.taggingDefaults.defaultPromptsMode || this.promptsMode;
        this.mergeAllSources = Boolean(this.taggingDefaults.mergeAllSources);
        this.rename = Boolean(this.taggingDefaults.renameFiles);
      }
      const pks = this.book.ids || [this.book.pk];
      try {
        const response = await HTTP.post("/admin/tag-write/preflight", {
          collection: this.book.collection,
          pks: pks.map(String),
          formats: this.taggingDefaults?.defaultFormats || ["COMIC_INFO"],
        });
        this.needConversion = response.data.needConversion || 0;
        this.deleteOriginal = response.data.deleteOriginal || false;
      } catch {
        this.needConversion = 0;
      }
    },
    startedMessage(skipped) {
      let message = "Online tagging started.";
      if (this.allSelectedPinned) {
        message = "Tagging by ID started.";
      } else if (this.anySelectedPinned) {
        message = "Tagging by ID & search started.";
      }
      if (skipped > 0) {
        message += ` ${skipped} comic${skipped === 1 ? "" : "s"} in read-only libraries skipped.`;
      }
      return message;
    },
    async submit() {
      if (this.actionDisabled) {
        return;
      }
      this.working = true;
      const pks = this.book.ids || [this.book.pk];
      try {
        const data = await this.startSession({
          collection: this.book.collection,
          pks,
          sources: this.orderedSelectedSources,
          mode: this.matchMode,
          promptsMode: this.promptsMode,
          deleteOriginal: this.deleteOriginal,
          mergeAllSources: this.mergeAllSources && this.canMerge,
          rename: this.rename,
          ids: this.pinnedIds,
        });
        useCommonStore().setSuccess(this.startedMessage(data?.skipped || 0));
        this.dialog = false;
        this.$emit("started");
      } catch (error) {
        useCommonStore().setErrors(error);
      } finally {
        this.working = false;
      }
    },
  },
};
</script>

<style scoped lang="scss">
.credentialWarning {
  font-size: 0.85em;
  color: rgb(var(--v-theme-warning));
  padding: 8px 0 0;
}

.existingIds {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 6px;
  margin-bottom: 12px;
}

.existingIdsLabel {
  font-size: 0.85em;
  color: rgb(var(--v-theme-textSecondary));
}

.pickSourceWarning {
  font-size: 0.85em;
  color: rgb(var(--v-theme-warning));
  padding: 8px 0 0;
}

.tagInfo {
  margin-top: 16px;
  font-size: 0.85em;
  color: rgb(var(--v-theme-textSecondary));
}

.comicCount {
  font-weight: 500;
}

.rateLimitWarning {
  color: rgb(var(--v-theme-warning));
  padding: 4px 0;
}

.timeEstimate {
  padding-top: 2px;
}

.conversionWarning {
  margin-top: 8px;
  padding: 8px;
  border-radius: 4px;
  background-color: rgba(var(--v-theme-warning), 0.1);
}

.conversionHelpText {
  font-size: 0.85em;
  color: rgb(var(--v-theme-textSecondary));
  margin-top: 4px;
}
</style>

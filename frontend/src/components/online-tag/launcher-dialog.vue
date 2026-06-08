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
          No online source credentials configured.
          <router-link :to="{ name: 'admin-tagging' }">
            Configure in Admin &rarr; Tagging
          </router-link>
        </div>
        <template v-else>
          <v-tabs v-if="idTaggable" v-model="activeTab" grow>
            <v-tab value="search">Search</v-tab>
            <v-tab value="byId">By ID</v-tab>
          </v-tabs>
          <v-card-subtitle v-else>Search</v-card-subtitle>
          <v-window v-model="activeTab" class="mt-4">
            <v-window-item value="search">
              <v-select
                v-model="sources"
                :items="sourceItems"
                label="Sources"
                multiple
                chips
                hide-details
                density="compact"
              />
              <v-select
                v-model="matchMode"
                :items="matchModeChoices"
                label="Match Mode"
                :hint="matchModeHint"
                persistent-hint
                density="compact"
                class="mt-3"
              />
              <v-select
                v-model="promptsMode"
                :items="promptsModeChoices"
                label="Prompts"
                :hint="promptsModeHint"
                persistent-hint
                density="compact"
                class="mt-3"
              />
              <div class="tagInfo">
                <div class="comicCount">
                  {{ comicCount }} comic{{ comicCount === 1 ? "" : "s" }} to
                  look up
                </div>
                <div v-if="rateLimitWarning" class="rateLimitWarning">
                  {{ rateLimitWarning }}
                </div>
                <div class="timeEstimate">
                  Estimated time: {{ timeEstimate }}
                </div>
                <div v-if="needConversion > 0" class="conversionWarning">
                  <div>
                    {{ needConversion }}
                    comic{{ needConversion === 1 ? "" : "s" }} will be converted
                    to CBZ.
                  </div>
                  <div class="conversionHelpText">
                    Writing tags to CBR, CB7, or CBT archives converts them to
                    CBZ. Enable this to delete the original file after
                    conversion.
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
            </v-window-item>
            <v-window-item v-if="idTaggable" value="byId">
              <div v-if="existingOptions.length" class="existingIds">
                <span class="existingIdsLabel">This comic's IDs:</span>
                <v-chip
                  v-for="opt in existingOptions"
                  :key="opt.value"
                  class="existingIdChip"
                  size="small"
                  variant="outlined"
                  @click="identifier = opt.value"
                >
                  {{ opt.title }}
                </v-chip>
              </div>
              <v-text-field
                v-model="identifier"
                label="Issue URL or ID"
                placeholder="Issue URL, metron:ID, or comicvine:ID"
                hint="Paste a Metron / Comic Vine issue URL, or enter metron:ID / comicvine:ID, or a bare ID."
                persistent-hint
                density="compact"
                @keyup.enter="submit"
              />
              <v-select
                v-if="bothConfigured"
                v-model="sourceChoice"
                :items="sourceChoices"
                label="Source"
                hint="Used only for a bare numeric ID. URLs and 4000- IDs detect the source automatically."
                persistent-hint
                density="compact"
                class="mt-3"
              />
              <div v-if="needsSourcePick" class="pickSourceWarning">
                Bare ID &mdash; choose Metron or Comic Vine.
              </div>
            </v-window-item>
          </v-window>
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
import { useAdminStore } from "@/stores/admin";
import { useCommonStore } from "@/stores/common";
import { useOnlineTagStore } from "@/stores/online-tag";

const MATCH_MODE_HINTS = {
  careful:
    "Only accepts high-confidence matches. Defers ambiguous results for manual review. ~5 requests/comic.",
  auto: "Balances accuracy and speed. Accepts good matches automatically, defers uncertain ones. ~3 requests/comic.",
  eager:
    "Accepts the best available match with minimal verification. Fastest but least precise. ~2 requests/comic.",
};
const PROMPTS_MODE_HINTS = {
  ask: "Pauses on ambiguous matches and asks you to choose the correct result.",
  never:
    "Skips all ambiguous matches without prompting. Unmatched comics are left unchanged.",
};

const SOURCE_RATES = {
  metron: { perMinute: 20, perHour: 1200, label: "Metron Cloud" },
  comicvine: { perMinute: 3, perHour: 200, label: "Comic Vine" },
};

const MATCH_MODE_CALLS_PER_COMIC = {
  eager: 2,
  auto: 3,
  careful: 5,
};

// Only these sources support online id tagging (mirrors the backend
// KNOWN_SOURCES); other identifiers a comic carries aren't offered.
const TAGGABLE_SOURCES = Object.freeze(new Set(["metron", "comicvine"]));
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
      activeTab: "search",
      // Search
      matchModeChoices: TAGGING_CHOICES.matchMode,
      promptsModeChoices: TAGGING_CHOICES.promptsMode,
      sources: ["metron", "comicvine"],
      matchMode: "auto",
      promptsMode: "ask",
      needConversion: 0,
      deleteOriginal: false,
      // By ID
      identifier: "",
      sourceChoice: "auto",
    };
  },
  computed: {
    ...mapState(useAdminStore, ["taggingDefaults"]),
    hasMetron() {
      return Boolean(this.taggingDefaults?.hasMetronCredentials);
    },
    hasComicvine() {
      return Boolean(this.taggingDefaults?.hasComicvineCredentials);
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
    idTaggable() {
      // Tag-by-id is per-issue: only when the selection is exactly one comic
      // (comicbox forbids --id on more than one path).
      return (
        this.book?.collection === "comics" &&
        (this.book?.ids?.length ?? 0) === 1
      );
    },
    // --- By ID ----------------------------------------------------------
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
    isBareInteger() {
      return /^\d+$/.test(this.identifier.trim());
    },
    needsSourcePick() {
      // A bare integer is ambiguous when both sources are configured; the
      // server can't auto-detect it, so require an explicit pick first.
      return (
        this.bothConfigured &&
        this.isBareInteger &&
        this.sourceChoice === "auto"
      );
    },
    // --- action button --------------------------------------------------
    actionLabel() {
      return this.activeTab === "byId" ? "Tag" : "Search";
    },
    searchDisabled() {
      const enabled = new Set(
        this.sourceItems.filter((s) => !s.props?.disabled).map((s) => s.value),
      );
      return !this.sources.some((s) => enabled.has(s));
    },
    byIdDisabled() {
      return !this.identifier.trim() || this.needsSourcePick;
    },
    actionDisabled() {
      if (this.allSourcesDisabled) return true;
      return this.activeTab === "byId"
        ? this.byIdDisabled
        : this.searchDisabled;
    },
    // --- search hints / estimates ---------------------------------------
    matchModeHint() {
      return MATCH_MODE_HINTS[this.matchMode] || "";
    },
    promptsModeHint() {
      return PROMPTS_MODE_HINTS[this.promptsMode] || "";
    },
    comicCount() {
      return this.book.childCount || 1;
    },
    activeSources() {
      const enabled = new Set(
        this.sourceItems.filter((s) => !s.props?.disabled).map((s) => s.value),
      );
      return this.sources.filter((s) => enabled.has(s));
    },
    callsPerComic() {
      return MATCH_MODE_CALLS_PER_COMIC[this.matchMode] || 3;
    },
    totalCalls() {
      return this.comicCount * this.callsPerComic;
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
        this.activeTab = "search";
        this.identifier = "";
        this.sourceChoice = "auto";
        this.initFromDefaults();
      }
    },
  },
  methods: {
    ...mapActions(useAdminStore, ["loadTaggingDefaults"]),
    ...mapActions(useOnlineTagStore, ["startSession", "tagById"]),
    async initFromDefaults() {
      await this.loadTaggingDefaults();
      if (this.taggingDefaults) {
        const enabled = new Set(
          this.sourceItems
            .filter((s) => !s.props?.disabled)
            .map((s) => s.value),
        );
        const defaults = this.taggingDefaults.defaultSources || [];
        this.sources = defaults.filter((s) => enabled.has(s));
        this.matchMode =
          this.taggingDefaults.defaultMatchMode || this.matchMode;
        this.promptsMode =
          this.taggingDefaults.defaultPromptsMode || this.promptsMode;
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
    submit() {
      if (this.actionDisabled) {
        return undefined;
      }
      return this.activeTab === "byId" ? this.doTagById() : this.doSearch();
    },
    async doSearch() {
      this.working = true;
      const pks = this.book.ids || [this.book.pk];
      try {
        await this.startSession({
          collection: this.book.collection,
          pks,
          sources: this.sources,
          mode: this.matchMode,
          promptsMode: this.promptsMode,
          deleteOriginal: this.deleteOriginal,
        });
        useCommonStore().setSuccess("Online tagging started.");
        this.dialog = false;
        this.$emit("started");
      } catch (error) {
        useCommonStore().setErrors(error);
      } finally {
        this.working = false;
      }
    },
    async doTagById() {
      this.working = true;
      const pk = this.book.pk || this.book.ids?.[0];
      const source = this.sourceChoice === "auto" ? "" : this.sourceChoice;
      try {
        const data = await this.tagById({
          collection: this.book.collection,
          pk,
          identifier: this.identifier.trim(),
          source,
        });
        useCommonStore().setSuccess(
          `Tagging ${data.source} #${data.id} queued.`,
        );
        this.dialog = false;
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

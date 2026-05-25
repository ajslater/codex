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
        <v-select
          v-model="sources"
          :items="sourceItems"
          label="Sources"
          multiple
          chips
          hide-details
          density="compact"
        />
        <div v-if="allSourcesDisabled" class="credentialWarning">
          No online source credentials configured.
          <router-link :to="{ name: 'admin-tagging' }">
            Configure in Admin &rarr; Tagging
          </router-link>
        </div>
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
            {{ comicCount }} comic{{ comicCount === 1 ? "" : "s" }} to look up
          </div>
          <div v-if="rateLimitWarning" class="rateLimitWarning">
            {{ rateLimitWarning }}
          </div>
          <div class="timeEstimate">Estimated time: {{ timeEstimate }}</div>
        </div>
      </v-card-text>
      <v-card-actions>
        <v-spacer />
        <v-btn variant="text" @click="dialog = false">Cancel</v-btn>
        <v-btn
          color="primary"
          variant="flat"
          :loading="starting"
          :disabled="startDisabled"
          @click="start"
        >
          Start
        </v-btn>
      </v-card-actions>
    </v-card>
  </v-dialog>
</template>

<script>
import { mapActions, mapState } from "pinia";

import { useAdminStore } from "@/stores/admin";
import { useCommonStore } from "@/stores/common";
import { useOnlineTagStore } from "@/stores/online-tag";

const MATCH_MODE_CHOICES = [
  { title: "Strict", value: "strict" },
  { title: "Normal", value: "normal" },
  { title: "Fast", value: "fast" },
];
const MATCH_MODE_HINTS = {
  strict:
    "Only accepts high-confidence matches. Defers ambiguous results for manual review. ~5 requests/comic.",
  normal:
    "Balances accuracy and speed. Accepts good matches automatically, defers uncertain ones. ~3 requests/comic.",
  fast: "Accepts the best available match with minimal verification. Fastest but least precise. ~2 requests/comic.",
};
const PROMPTS_MODE_CHOICES = [
  { title: "Ask", value: "ask" },
  { title: "Never", value: "never" },
];
const PROMPTS_MODE_HINTS = {
  ask: "Pauses on ambiguous matches and asks you to choose the correct result.",
  never:
    "Skips all ambiguous matches without prompting. Unmatched comics are left unchanged.",
};

const SOURCE_RATES = {
  metron: { perMinute: 20, label: "Metron (20 req/min)" },
  comicvine: { perMinute: 3, label: "Comic Vine (200 req/hr)" },
};

const MATCH_MODE_CALLS_PER_COMIC = {
  fast: 2,
  normal: 3,
  strict: 5,
};

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
    size: {
      type: String,
      default: "default",
    },
  },
  emits: ["started"],
  data() {
    return {
      dialog: false,
      starting: false,
      matchModeChoices: MATCH_MODE_CHOICES,
      promptsModeChoices: PROMPTS_MODE_CHOICES,
      sources: ["metron", "comicvine"],
      matchMode: "normal",
      promptsMode: "ask",
    };
  },
  computed: {
    ...mapState(useAdminStore, ["taggingDefaults"]),
    sourceItems() {
      return [
        {
          title: "Metron",
          value: "metron",
          props: this.taggingDefaults?.hasMetronCredentials
            ? {}
            : { disabled: true },
        },
        {
          title: "Comic Vine",
          value: "comicvine",
          props: this.taggingDefaults?.hasComicvineCredentials
            ? {}
            : { disabled: true },
        },
      ];
    },
    allSourcesDisabled() {
      return this.sourceItems.every((s) => s.props?.disabled);
    },
    startDisabled() {
      if (this.allSourcesDisabled) return true;
      const enabled = new Set(
        this.sourceItems.filter((s) => !s.props?.disabled).map((s) => s.value),
      );
      return !this.sources.some((s) => enabled.has(s));
    },
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
        if (rate && this.totalCalls > rate.perMinute) {
          warnings.push(rate.label);
        }
      }
      if (warnings.length === 0) return "";
      return `Exceeds rate limits for: ${warnings.join(", ")}`;
    },
  },
  watch: {
    dialog(to) {
      if (to) this.initFromDefaults();
    },
  },
  methods: {
    ...mapActions(useAdminStore, ["loadTaggingDefaults"]),
    ...mapActions(useOnlineTagStore, ["startSession"]),
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
    },
    async start() {
      this.starting = true;
      const pks = this.book.ids || [this.book.pk];
      try {
        await this.startSession({
          group: this.book.group,
          pks,
          sources: this.sources,
          mode: this.matchMode,
          promptsMode: this.promptsMode,
        });
        useCommonStore().setSuccess("Online tagging started.");
        this.dialog = false;
        this.$emit("started");
      } catch (error) {
        useCommonStore().setErrors(error);
      } finally {
        this.starting = false;
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
</style>

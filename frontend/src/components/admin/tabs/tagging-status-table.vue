<!--
  Live online-tagging status table for the admin Tagging tab.

  Renders the daemon's session snapshot (online-tag store): a batch-progress
  header with a live ETA countdown, a per-source strip showing run order and
  rate-limit countdowns, and a capped, virtualized per-comic table. The whole
  block hides until a scan has run (snapshot === null); the snapshot's
  ``active`` flag flips to false when a batch finishes, leaving the final tally
  on screen.

  Per-comic "needs review" is overlaid from the live pending-prompt list so a
  fresh prompt surfaces here even before the next snapshot refresh; the Review
  button opens the existing match-review popup.
-->
<template>
  <AdminSection v-if="snapshot" title="Online Tagging Status" class="tagStatus">
    <template #actions>
      <!-- Running: pause (keeps the remainder resumable). -->
      <v-btn
        v-if="snapshot.active && pausing"
        size="small"
        variant="text"
        color="warning"
        disabled
        loading
      >
        Pausing…
      </v-btn>
      <ConfirmDialog
        v-else-if="snapshot.active"
        button-text="Pause"
        title-text="Pause Online Tagging"
        text="Pause the current online tagging session? Comics already tagged keep their tags; the rest can be resumed later. Prompts awaiting review are kept."
        confirm-text="Pause"
        color="warning"
        variant="tonal"
        size="small"
        :block="false"
        :prepend-icon="mdiPause"
        @confirm="confirmPause"
      />
      <!-- Paused/finished: resume the remainder and/or dismiss the table. -->
      <template v-else>
        <v-btn
          v-if="resumable"
          size="small"
          variant="tonal"
          color="primary"
          :prepend-icon="mdiPlay"
          :loading="resuming"
          :disabled="resuming"
          @click="confirmResume"
        >
          Resume
        </v-btn>
        <ConfirmDialog
          button-text="Dismiss"
          title-text="Dismiss Tagging Status"
          text="Clear this session from the status table? Comics keep their tags and prompts awaiting review are kept; a paused session can no longer be resumed."
          confirm-text="Dismiss"
          variant="text"
          size="small"
          :block="false"
          :prepend-icon="mdiClose"
          @confirm="confirmDismiss"
        />
      </template>
    </template>
    <template #hint>
      Live progress of the current online tagging batch.
    </template>

    <!-- Batch header: state, progress, ETA, tallies -->
    <div class="batchHeader">
      <div class="batchLine">
        <v-chip size="small" :color="stateColor" variant="flat">
          {{ stateLabel }}
        </v-chip>
        <span class="progressText">{{ nf(completed) }} / {{ nf(total) }}</span>
        <span v-if="etaText" class="eta">{{ etaText }}</span>
      </div>
      <v-progress-linear
        :model-value="progressPct"
        :indeterminate="indeterminate"
        color="primary"
        height="6"
        rounded
      />
      <div class="tallies">
        <span class="tally matched">{{ nf(batch.matched) }} matched</span>
        <span class="tally review">{{ nf(reviewCount) }} need review</span>
        <span class="tally">{{ nf(batch.queued) }} queued</span>
        <span class="tally">{{ nf(batch.noMatch) }} no match</span>
        <span v-if="batch.error" class="tally error">
          {{ nf(batch.error) }} error
        </span>
      </div>
    </div>

    <!-- Sources strip: run order + rate-limit countdowns -->
    <div class="sourcesStrip">
      <div
        v-for="(src, idx) in snapshot.sources"
        :key="src.source"
        class="sourceChip"
        :class="{ limited: rateText(src) }"
      >
        <span class="sourceOrder">{{ idx + 1 }}</span>
        <span class="sourceName">{{ sourceLabel(src.source) }}</span>
        <span class="sourceRate">{{ src.ratePerMinute }}/min</span>
        <span v-if="rateText(src)" class="sourceLimit">
          <v-icon :icon="mdiTimerSand" size="x-small" />
          {{ rateText(src) }}
        </span>
      </div>
    </div>

    <!-- Per-comic table -->
    <v-data-table-virtual
      class="comicsTable"
      :headers="headers"
      :items="rows"
      item-value="pk"
      :mobile="$vuetify.display.xs"
      fixed-header
      height="420"
      density="compact"
    >
      <template #[`item.status`]="{ item }">
        <span class="statusCell" :style="{ color: statusColor(item.status) }">
          <v-progress-circular
            v-if="item.status === 'in_flight'"
            indeterminate
            size="14"
            width="2"
            class="mr-1"
          />
          <v-icon
            v-else
            :icon="statusIcon(item.status)"
            size="small"
            class="mr-1"
          />
          {{ statusLabel(item.status) }}
        </span>
      </template>
      <template #[`item.path`]="{ item }">
        <span class="pathCell" :title="item.path">
          {{ filename(item.path) }}
        </span>
      </template>
      <template #[`item.wonSource`]="{ item }">
        <span v-if="item.wonSource">{{ sourceLabel(item.wonSource) }}</span>
        <span v-else class="muted">—</span>
      </template>
      <template #[`item.action`]="{ item }">
        <v-btn
          v-if="item.status === 'needs_review'"
          variant="tonal"
          size="x-small"
          color="primary"
          @click="openReview"
        >
          Review
        </v-btn>
      </template>
    </v-data-table-virtual>
    <p
      v-if="snapshot.comicCount > snapshot.shownCount"
      class="adminHint capNote"
    >
      Showing {{ nf(snapshot.shownCount) }} of {{ nf(snapshot.comicCount) }}
      comics — in-flight, review, error, and queued rows are listed first.
    </p>
  </AdminSection>
</template>

<script>
import {
  mdiAccountCancel,
  mdiAccountCheck,
  mdiAlertCircleOutline,
  mdiCheckCircleOutline,
  mdiClockOutline,
  mdiClose,
  mdiHelpCircleOutline,
  mdiMagnify,
  mdiPause,
  mdiPlay,
  mdiTimerSand,
} from "@mdi/js";
import { mapActions, mapState, mapWritableState } from "pinia";

import { nf } from "@/components/admin/status-helpers";
import { useNowTimer } from "@/components/admin/use-now-timer";
import AdminSection from "@/components/admin/tabs/admin-section.vue";
import ConfirmDialog from "@/components/confirm-dialog.vue";
import { useOnlineTagStore } from "@/stores/online-tag";

// Friendly display names for online tagging sources (mirrors prompt-popup).
const SOURCE_LABELS = Object.freeze({
  metron: "Metron Cloud",
  comicvine: "Comic Vine",
});

// Per-status display: label, theme color token, and icon. ``in_flight`` renders
// a spinner instead of an icon (handled in the template).
const STATUS_META = Object.freeze({
  in_flight: { label: "Looking up", color: "primary", icon: mdiMagnify },
  needs_review: {
    label: "Needs review",
    color: "warning",
    icon: mdiHelpCircleOutline,
  },
  matched: { label: "Matched", color: "success", icon: mdiCheckCircleOutline },
  no_match: {
    label: "No match",
    color: "textSecondary",
    icon: mdiClockOutline,
  },
  error: { label: "Error", color: "error", icon: mdiAlertCircleOutline },
  queued: { label: "Queued", color: "textSecondary", icon: mdiClockOutline },
  // Outcomes of admin match-review actions, overlaid by the server.
  user_matched: {
    label: "User matched",
    color: "success",
    icon: mdiAccountCheck,
  },
  user_skipped: {
    label: "User skipped",
    color: "textSecondary",
    icon: mdiAccountCancel,
  },
});

/** Whole seconds from `now` (ms) until an epoch-seconds target, clamped at 0. */
const secondsUntil = (epoch, now) => {
  if (!epoch) return null;
  return Math.max(0, Math.round((epoch * 1000 - now) / 1000));
};

/** Coarse "~Xh Ym" / "~Xm Ys" / "~Ys" remaining string. */
const formatRemaining = (secs) => {
  if (secs >= 3600) {
    const h = Math.floor(secs / 3600);
    const m = Math.round((secs % 3600) / 60);
    return m ? `~${h}h ${m}m` : `~${h}h`;
  }
  if (secs >= 60) {
    const m = Math.floor(secs / 60);
    const s = secs % 60;
    return s ? `~${m}m ${s}s` : `~${m}m`;
  }
  return `~${secs}s`;
};

/** "m:ss" (>= 60s) or "Ns" countdown string. */
const formatCountdown = (secs) => {
  if (secs < 60) return `${secs}s`;
  const m = Math.floor(secs / 60);
  const s = secs % 60;
  return `${m}:${String(s).padStart(2, "0")}`;
};

export default {
  name: "AdminTaggingStatusTable",
  components: { AdminSection, ConfirmDialog },
  setup() {
    const { now } = useNowTimer();
    return { now };
  },
  data() {
    return {
      mdiClose,
      mdiPause,
      mdiPlay,
      mdiTimerSand,
      // True from clicking Pause until the daemon reports the scan stopped.
      // The cancel only takes effect between comics, so during a rate-limit
      // wait this "Pausing…" state can linger a bit — honestly so.
      pausing: false,
      // True from clicking Resume until the daemon reports the scan active.
      resuming: false,
      headers: [
        { title: "Comic", key: "path", align: "start" },
        { title: "Status", key: "status", align: "start" },
        { title: "Source", key: "wonSource", align: "start", sortable: false },
        { title: "", key: "action", align: "end", sortable: false },
      ],
    };
  },
  computed: {
    ...mapState(useOnlineTagStore, [
      "snapshot",
      "pendingPrompts",
      "locallyResolved",
    ]),
    ...mapWritableState(useOnlineTagStore, ["promptDialogOpen"]),
    batch() {
      return this.snapshot?.batch || {};
    },
    // A paused/interrupted session still has unprocessed comics to resume.
    resumable() {
      return Boolean(this.snapshot?.resumable);
    },
    stateLabel() {
      if (this.snapshot?.active) return "Tagging";
      return this.resumable ? "Paused" : "Finished";
    },
    stateColor() {
      if (this.snapshot?.active) return "primary";
      return this.resumable ? "warning" : undefined;
    },
    total() {
      return this.batch.total || 0;
    },
    completed() {
      return this.batch.completed || 0;
    },
    indeterminate() {
      return Boolean(this.snapshot?.active) && !this.total;
    },
    progressPct() {
      if (!this.total || this.indeterminate) return 0;
      return (100 * this.completed) / this.total;
    },
    etaText() {
      if (!this.snapshot?.active) return "";
      const secs = secondsUntil(this.batch.etaEpoch, this.now);
      if (secs === null) return "";
      return secs <= 0 ? "finishing…" : `${formatRemaining(secs)} left`;
    },
    // pk -> fingerprint for comics still awaiting review, from the live prompt
    // list (fresher than the snapshot between refreshes).
    reviewByPk() {
      const map = new Map();
      for (const prompt of this.pendingPrompts || []) {
        if (prompt.pk != null) map.set(prompt.pk, prompt.fingerprint);
      }
      return map;
    },
    reviewCount() {
      // Prefer the live prompt count; fall back to the snapshot tally.
      return this.pendingPrompts?.length || this.batch.needsReview || 0;
    },
    rows() {
      const comics = this.snapshot?.comics || [];
      return comics.map((c) => ({
        ...c,
        status: this.effectiveStatus(c),
      }));
    },
  },
  watch: {
    // Clear the transient pause/resume states once the scan's actual state
    // catches up: pausing ends when the scan stops, resuming when it starts.
    "snapshot.active"(active) {
      if (active) {
        this.resuming = false;
      } else {
        this.pausing = false;
      }
    },
  },
  mounted() {
    // Pull the current snapshot when the tab opens; socket task.progress keeps
    // it fresh thereafter while this tab is active. Promise.resolve guards
    // against a non-thenable return (e.g. stubbed action under test).
    Promise.resolve(useOnlineTagStore().loadSnapshot()).catch(() => {});
  },
  methods: {
    ...mapActions(useOnlineTagStore, [
      "pauseSession",
      "resumeSession",
      "dismissSession",
    ]),
    nf,
    async confirmPause() {
      this.pausing = true;
      try {
        await this.pauseSession();
      } catch {
        this.pausing = false;
      }
    },
    async confirmResume() {
      this.resuming = true;
      try {
        await this.resumeSession();
      } catch {
        this.resuming = false;
      }
    },
    async confirmDismiss() {
      try {
        await this.dismissSession();
      } catch {
        // Best-effort; the daemon clears the cache regardless.
      }
    },
    effectiveStatus(comic) {
      // Precedence: a comic still in the live prompt queue needs review
      // (covers a drifted re-queue); then an optimistic local resolution that
      // the daemon hasn't recorded yet; otherwise the server's status (which
      // already carries user_matched/user_skipped once reconciled).
      if (this.reviewByPk.has(comic.pk)) return "needs_review";
      return this.locallyResolved[comic.pk] ?? comic.status;
    },
    sourceLabel(source) {
      return SOURCE_LABELS[source] || source;
    },
    filename(path) {
      if (!path) return "Unknown";
      const parts = path.split("/");
      return parts[parts.length - 1];
    },
    statusLabel(status) {
      return STATUS_META[status]?.label || status;
    },
    statusIcon(status) {
      return STATUS_META[status]?.icon || mdiClockOutline;
    },
    statusColor(status) {
      const token = STATUS_META[status]?.color || "textSecondary";
      return `rgb(var(--v-theme-${token}))`;
    },
    rateText(src) {
      if (!src.rateLimited) return "";
      const secs = secondsUntil(src.retryAtEpoch, this.now);
      if (secs === null) return "";
      return secs <= 0 ? "retrying…" : `retry ${formatCountdown(secs)}`;
    },
    openReview() {
      this.promptDialogOpen = true;
    },
  },
};
</script>

<style scoped lang="scss">
@use "@/components/admin/tabs/design.scss" as d;

.tagStatus {
  margin-bottom: d.$space-4;
}

.batchHeader {
  display: flex;
  flex-direction: column;
  gap: d.$space-2;
}

.batchLine {
  display: flex;
  align-items: center;
  gap: d.$space-3;
}

.progressText {
  font-variant-numeric: tabular-nums;
  font-weight: 500;
}

.eta {
  color: rgb(var(--v-theme-textSecondary));
}

.tallies {
  display: flex;
  flex-wrap: wrap;
  gap: d.$space-3;
  font-size: 0.85rem;
}

.tally.matched {
  color: rgb(var(--v-theme-success));
}

.tally.review {
  color: rgb(var(--v-theme-warning));
}

.tally.error {
  color: rgb(var(--v-theme-error));
}

.sourcesStrip {
  display: flex;
  flex-wrap: wrap;
  gap: d.$space-2;
  margin: d.$space-3 0;
}

.sourceChip {
  display: flex;
  align-items: center;
  gap: d.$space-2;
  padding: d.$space-1 d.$space-3;
  border: 1px solid rgba(var(--v-theme-on-surface), 0.16);
  border-radius: 999px;
  font-size: 0.85rem;
}

.sourceChip.limited {
  border-color: rgb(var(--v-theme-warning));
}

.sourceOrder {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 1.4em;
  height: 1.4em;
  border-radius: 50%;
  background-color: rgba(var(--v-theme-on-surface), 0.12);
  font-size: 0.75rem;
  font-weight: 600;
}

.sourceName {
  font-weight: 500;
}

.sourceRate {
  color: rgb(var(--v-theme-textSecondary));
}

.sourceLimit {
  color: rgb(var(--v-theme-warning));
  font-variant-numeric: tabular-nums;
}

.comicsTable {
  background-color: inherit;
}

.statusCell {
  display: inline-flex;
  align-items: center;
  white-space: nowrap;
}

.pathCell {
  display: inline-block;
  max-width: 32ch;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  vertical-align: middle;
}

.muted {
  color: rgb(var(--v-theme-textSecondary));
}

.capNote {
  margin-top: d.$space-2;
}
</style>

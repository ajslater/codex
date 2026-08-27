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
          :button-text="dismissLabel"
          :title-text="dismissTitle"
          :text="dismissText"
          :confirm-text="dismissConfirm"
          variant="text"
          size="small"
          :block="false"
          :prepend-icon="mdiClose"
          @confirm="confirmDismiss"
        />
      </template>
    </template>
    <template #hint>
      Live progress of the current online tagging session.
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
        <span v-if="dailyText(src)" class="sourceRate">
          {{ dailyText(src) }}
        </span>
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
      <template #[`item.path`]="{ item }">
        <span class="pathCell" :title="pathTitle(item)">
          <v-progress-circular
            v-if="item.live"
            indeterminate
            size="12"
            width="2"
            class="liveSpinner mr-1"
          />
          {{ filename(item.path) }}
        </span>
      </template>
      <template
        v-for="source in selectedSources"
        :key="source"
        #[`item.${sourceKey(source)}`]="{ item }"
      >
        <span
          v-if="item.cells[source]"
          class="statusCell"
          :style="{ color: statusColor(item.cells[source]) }"
          :title="statusHint(item.cells[source])"
        >
          <v-progress-circular
            v-if="item.cells[source] === 'in_flight'"
            indeterminate
            size="14"
            width="2"
            class="mr-1"
          />
          <v-icon
            v-else
            :icon="statusIcon(item.cells[source])"
            size="small"
            class="mr-1"
          />
          {{ statusLabel(item.cells[source]) }}
        </span>
        <span
          v-else
          class="muted"
          title="This source did not report on this comic."
        >
          —
        </span>
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
  mdiSkipNext,
  mdiTimerSand,
} from "@mdi/js";
import { mapActions, mapState, mapWritableState } from "pinia";

import { nf } from "@/components/admin/status-helpers";
import { useNowTimer } from "@/components/admin/use-now-timer";
import AdminSection from "@/components/admin/tabs/admin-section.vue";
import ConfirmDialog from "@/components/confirm-dialog.vue";
import { sourceLabel } from "@/components/online-tag/source-labels";
import { useCommonStore } from "@/stores/common";
import { useOnlineTagStore } from "@/stores/online-tag";

// Per-status display: label, theme color token, icon, and a tooltip hint.
// ``in_flight`` renders a spinner instead of an icon (handled in the
// template). ``skipped`` is presentation-only — derived in cellStatus for a
// first-wins source the scan never needed, never sent by the server.
const STATUS_META = Object.freeze({
  in_flight: {
    label: "Looking up",
    color: "primary",
    icon: mdiMagnify,
    hint: "This source is being queried right now.",
  },
  // This source is throttled and sitting out its retry wait. The countdown
  // itself stays in the sources strip, where it ticks in one place.
  waiting: {
    label: "Waiting",
    color: "warning",
    icon: mdiTimerSand,
    hint: "This source is rate limited — the lookup resumes when it allows.",
  },
  needs_review: {
    label: "Needs review",
    color: "warning",
    icon: mdiHelpCircleOutline,
    hint: "This source found candidates that need your pick.",
  },
  matched: {
    label: "Matched",
    color: "success",
    icon: mdiCheckCircleOutline,
    hint: "This source matched the comic and wrote its tags.",
  },
  no_match: {
    label: "No match",
    color: "textSecondary",
    icon: mdiClockOutline,
    hint: "This source found no confident match.",
  },
  error: {
    label: "Error",
    color: "error",
    icon: mdiAlertCircleOutline,
    hint: "The comic errored before finishing.",
  },
  queued: {
    label: "Queued",
    color: "textSecondary",
    icon: mdiClockOutline,
    hint: "This source hasn't looked the comic up yet.",
  },
  skipped: {
    label: "Skipped",
    color: "textSecondary",
    icon: mdiSkipNext,
    hint: "Not searched — an earlier source already matched this comic.",
  },
  // Outcomes of admin match-review actions, overlaid by the server.
  user_matched: {
    label: "User matched",
    color: "success",
    icon: mdiAccountCheck,
    hint: "You picked this source's match.",
  },
  user_skipped: {
    label: "User skipped",
    color: "textSecondary",
    icon: mdiAccountCancel,
    hint: "You skipped this source's prompt.",
  },
});

// Cell values that only make sense while a scan is running. Mirrors the
// backend's LIVE_SOURCE_STATUSES; a snapshot cached by an older version (the
// tagging cache is file-backed with no TTL) can still carry one.
const LIVE_CELL_STATUSES = new Set(["in_flight", "waiting"]);

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
    // The sources this session actually runs, in priority order — one status
    // column each, so a source the admin didn't select never takes up room.
    selectedSources() {
      return this.batch.sources || [];
    },
    headers() {
      return [
        // Comic claims all slack (width 100% + the max-width:0 cell trick) so
        // the filename fills every spare pixel before truncating; the other
        // columns stay shrink-to-fit around their content (or just the title).
        {
          title: "Comic",
          key: "path",
          align: "start",
          sortable: false,
          width: "100%",
          cellProps: { class: "pathColumn" },
        },
        ...this.selectedSources.map((source) => ({
          title: this.sourceLabel(source),
          key: this.sourceKey(source),
          align: "start",
          sortable: false,
          // Keep "Metron Cloud" on one line. The Comic column claims all the
          // slack (width 100%), which otherwise squeezes these columns down
          // to their narrowest word and stacks the header. Comic yields the
          // width back, truncating its filename instead. Vuetify pairs its
          // nowrap rule with an ellipsis, so a viewport too narrow for the
          // full name clips it rather than ever stacking it.
          nowrap: true,
        })),
        { title: "", key: "action", align: "end", sortable: false },
      ];
    },
    // A paused/interrupted session still has unprocessed comics to resume.
    resumable() {
      return Boolean(this.snapshot?.resumable);
    },
    // The close action only renders when the scan isn't active, so `resumable`
    // (paused) means the session is *not finished* — clearing it is a "Cancel",
    // not a "Dismiss". The confirm label stays distinct from the footer's own
    // "Cancel" back button to avoid an ambiguous Cancel/Cancel pair.
    dismissLabel() {
      return this.resumable ? "Cancel" : "Dismiss";
    },
    dismissTitle() {
      return this.resumable
        ? "Cancel Tagging Session"
        : "Dismiss Tagging Status";
    },
    dismissText() {
      return this.resumable
        ? "Cancel this paused online tagging session? Comics already tagged keep their tags and prompts awaiting review are kept, but the remaining comics can no longer be resumed."
        : "Clear this session from the status table? Comics keep their tags and prompts awaiting review are kept; a paused session can no longer be resumed.";
    },
    dismissConfirm() {
      return this.resumable ? "Cancel Session" : "Dismiss";
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
    // pk -> the source(s) whose prompt is still awaiting review, from the live
    // prompt list (fresher than the snapshot between refreshes). Under
    // merge-all-sources one comic can be waiting on a prompt from each source.
    reviewByPk() {
      const map = new Map();
      for (const prompt of this.pendingPrompts || []) {
        if (prompt.pk == null) continue;
        const sources = map.get(prompt.pk) || [];
        if (prompt.source && !sources.includes(prompt.source)) {
          sources.push(prompt.source);
        }
        map.set(prompt.pk, sources);
      }
      return map;
    },
    reviewCount() {
      // Prefer the live prompt count; fall back to the snapshot tally.
      return this.pendingPrompts?.length || this.batch.needsReview || 0;
    },
    mergeAllSources() {
      return Boolean(this.batch.mergeAllSources);
    },
    // Only a running scan can be looking anything up.
    liveScan() {
      return Boolean(this.snapshot?.active);
    },
    rows() {
      const comics = this.snapshot?.comics || [];
      return comics.map((c) => {
        const row = { ...c, status: this.effectiveStatus(c) };
        // The one comic being looked up right now — the daemon marks exactly
        // one, and only while the scan is running.
        row.live = this.liveScan && row.status === "in_flight";
        // Resolve every source cell once per row instead of per template read.
        row.cells = Object.fromEntries(
          this.selectedSources.map((s) => [s, this.cellStatus(row, s)]),
        );
        return row;
      });
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
      } catch (error) {
        this.pausing = false;
        useCommonStore().setErrors(error);
      }
    },
    async confirmResume() {
      this.resuming = true;
      try {
        await this.resumeSession();
      } catch (error) {
        // Say why nothing happened. A resume can be refused (another scan
        // started first, or the remainder is gone) and silently dropping
        // that leaves the button looking broken.
        this.resuming = false;
        useCommonStore().setErrors(error);
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
      return this.locallyResolved[comic.pk]?.status ?? comic.status;
    },
    // What one source did with one comic, or null for "unknown".
    // Mirrors effectiveStatus's precedence, one source deep.
    cellStatus(item, source) {
      if (this.reviewByPk.get(item.pk)?.includes(source)) return "needs_review";
      const local = this.locallyResolved[item.pk]?.sources?.[source];
      if (local) return local;
      // Optional chaining keeps a snapshot cached before per-source columns
      // (the tagging cache outlives an upgrade) rendering instead of throwing.
      const status = item.sourceStatuses?.[source];
      if (status) {
        // A paused, finished or crashed session is querying nothing. The
        // daemon scrubs these on the way out, but a snapshot frozen by a hard
        // kill still carries them until it next starts — the same defense
        // rateText applies to the retry countdowns.
        if (!this.liveScan && LIVE_CELL_STATUSES.has(status)) return "queued";
        return status;
      }
      return this.cellFallback(item, source);
    },
    // A source with no recorded cell still has a describable state, derived
    // from the row it sits on. A bare em-dash told the admin nothing.
    cellFallback(item) {
      // Queued comic, or a source the in-flight comic's lookup hasn't reached.
      if (item.status === "queued" || item.status === "in_flight") {
        return "queued";
      }
      // Every searched source came up empty; a cell-less one (a silently
      // failed search, or a snapshot cached before per-source columns)
      // reads the same as the row.
      if (item.status === "no_match") return "no_match";
      // Under first-wins a matched comic's remaining sources were never
      // searched. Only when some cell exists, though — a pre-upgrade
      // snapshot has no cells at all, and there the winner is unknowable.
      if (
        item.status === "matched" &&
        !this.mergeAllSources &&
        Object.keys(item.sourceStatuses || {}).length > 0
      ) {
        return "skipped";
      }
      return null;
    },
    sourceLabel,
    // Column keys are namespaced so a source id can never collide with a row
    // field name (path, status, action).
    sourceKey(source) {
      return `src_${source}`;
    },
    pathTitle(item) {
      return item.live
        ? `${item.path} — Codex is looking this comic up right now`
        : item.path;
    },
    filename(path) {
      if (!path) return "Unknown";
      const parts = path.split("/");
      return parts[parts.length - 1];
    },
    statusLabel(status) {
      return STATUS_META[status]?.label || status;
    },
    statusHint(status) {
      return STATUS_META[status]?.hint || "";
    },
    statusIcon(status) {
      return STATUS_META[status]?.icon || mdiClockOutline;
    },
    statusColor(status) {
      const token = STATUS_META[status]?.color || "textSecondary";
      return `rgb(var(--v-theme-${token}))`;
    },
    rateText(src) {
      // A paused or finished session is retrying nothing, so it never shows a
      // countdown — the daemon disarms these, but a snapshot cached by an
      // older version can still carry a live-looking deadline.
      if (!this.snapshot?.active || !src.rateLimited) return "";
      const secs = secondsUntil(src.retryAtEpoch, this.now);
      if (secs === null) return "";
      return secs <= 0 ? "retrying…" : `retry ${formatCountdown(secs)}`;
    },
    dailyText(src) {
      // Live account budget from Metron's X-RateLimit-* headers; the
      // daily limit varies by donor tier, so show it once it's known.
      const remaining = src.sustainedRemaining;
      const limit = src.sustainedLimit;
      if (remaining != null && limit != null) {
        return `${nf(remaining)}/${nf(limit)} day`;
      }
      if (limit != null) return `${nf(limit)}/day`;
      if (remaining != null) return `${nf(remaining)} left today`;
      return "";
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

// The Comic column carries width:100%, so this cell absorbs all the slack the
// other (shrink-to-fit) columns leave. ``max-width: 0`` is the canonical trick
// that lets a flexible table cell actually clip: without it the cell grows to
// its content and never truncates. The full path stays available via title.
.comicsTable :deep(td.pathColumn) {
  max-width: 0;
  overflow: hidden;
  white-space: nowrap;
  text-overflow: ellipsis;
}

.pathCell {
  display: inline;
}

/* The path cell is inline (so its ellipsis works), which drops the spinner
   onto the text baseline; nudge it back onto the cap height. */
.liveSpinner {
  vertical-align: text-bottom;
  color: rgb(var(--v-theme-primary));
}

.muted {
  color: rgb(var(--v-theme-textSecondary));
}

.capNote {
  margin-top: d.$space-2;
}
</style>

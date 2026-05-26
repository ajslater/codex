<template>
  <div id="restore" class="adminContainer">
    <!-- Description card -->
    <div class="adminGroup">
      <div class="adminGroupHeader">
        <h3>User Data Sidecar</h3>
      </div>
      <div class="adminCard">
        <p class="adminCardDesc paragraph">
          Codex mirrors every user-bound row — accounts, bookmarks, favorites,
          browser settings, library definitions, admin flags — into a separate
          SQLite file alongside your config. If the main database is ever lost
          or rebuilt from a filesystem scan, you can restore everything users
          care about from this file.
        </p>
        <p class="adminCardDesc paragraph">
          The file lives at <code>user_data.sqlite</code> inside your Codex
          config directory. Copy it offsite to back it up, or carry it to a new
          host before re-importing your library.
        </p>
      </div>
    </div>

    <!-- Restore action -->
    <div class="adminGroup">
      <div class="adminGroupHeader">
        <h3>Restore</h3>
      </div>
      <div class="adminCard">
        <p class="adminCardDesc paragraph">
          Replay every sidecar row into the main database. Rows whose targets
          can't be resolved (a deleted comic, a renamed tag) are logged and
          skipped — the operation never aborts. Re-running the restore is safe;
          it's idempotent.
        </p>
        <div class="restoreActions">
          <v-checkbox
            v-model="dryRun"
            label="Dry run (report only, don't write)"
            hide-details
            density="compact"
            :disabled="isRunning"
          />
          <ConfirmDialog
            :key="dryRun ? 'dry' : 'live'"
            :button-text="dryRun ? 'Preview Restore' : 'Restore Now'"
            title-text="Restore User Data"
            :text="confirmText"
            confirm-text="Restore"
            :block="false"
            :disabled="isRunning"
            @confirm="runRestore"
          />
        </div>
        <v-progress-linear
          v-if="isRunning"
          indeterminate
          color="primary"
          class="restoreProgress"
        />
      </div>
    </div>

    <!-- Result -->
    <div v-if="report" class="adminGroup">
      <div class="adminGroupHeader">
        <h3>{{ resultTitle }}</h3>
      </div>
      <div class="adminCard">
        <h4 class="resultSubhead">Restored</h4>
        <table v-if="writtenRows.length" class="resultTable">
          <tr v-for="[label, count] in writtenRows" :key="label">
            <td>{{ label }}</td>
            <td class="resultCount">{{ count }}</td>
          </tr>
        </table>
        <div v-else class="adminCardDesc">Nothing to restore.</div>
      </div>
      <div v-if="skippedRows.length" class="adminCard">
        <h4 class="resultSubhead resultSkipped">Skipped</h4>
        <table class="resultTable">
          <tr v-for="[label, count] in skippedRows" :key="label">
            <td>{{ label }}</td>
            <td class="resultCount">{{ count }}</td>
          </tr>
        </table>
        <div v-if="report.unmatched && report.unmatched.length">
          <button class="expandToggle" @click="showUnmatched = !showUnmatched">
            <v-icon size="small">
              {{ showUnmatched ? mdiChevronUp : mdiChevronDown }}
            </v-icon>
            <span>{{ unmatchedToggleLabel }}</span>
          </button>
          <v-expand-transition>
            <pre v-if="showUnmatched" class="unmatchedLog">{{
              unmatchedPreview
            }}</pre>
          </v-expand-transition>
        </div>
      </div>
      <div v-if="report.log_path" class="adminCard">
        <div class="adminCardDesc">
          Full log written to <code>{{ report.log_path }}</code>
        </div>
      </div>
    </div>
  </div>
</template>

<script>
import { mdiChevronDown, mdiChevronUp } from "@mdi/js";
import { mapActions } from "pinia";

import ConfirmDialog from "@/components/confirm-dialog.vue";
import { useAdminStore } from "@/stores/admin";

const UNMATCHED_PREVIEW_LIMIT = 50;

export default {
  name: "AdminRestoreTab",
  components: { ConfirmDialog },
  data() {
    return {
      mdiChevronDown,
      mdiChevronUp,
      dryRun: false,
      isRunning: false,
      report: undefined,
      showUnmatched: false,
    };
  },
  computed: {
    confirmText() {
      return this.dryRun
        ? "Preview only — no changes will be written."
        : "Overwrite current user data with the sidecar contents. Existing users, bookmarks, favorites, and settings will be replaced. Continue?";
    },
    resultTitle() {
      return this.dryRunReport ? "Dry-Run Report" : "Restore Result";
    },
    dryRunReport() {
      return this.report?._dryRun;
    },
    writtenRows() {
      return this.toRows(this.report?.written);
    },
    skippedRows() {
      return this.toRows(this.report?.skipped);
    },
    unmatchedPreview() {
      const log = this.report?.unmatched ?? [];
      if (log.length <= UNMATCHED_PREVIEW_LIMIT) {
        return log.join("\n");
      }
      const head = log.slice(0, UNMATCHED_PREVIEW_LIMIT).join("\n");
      const remaining = log.length - UNMATCHED_PREVIEW_LIMIT;
      return `${head}\n… and ${remaining} more (see full log)`;
    },
    unmatchedToggleLabel() {
      const total = this.report?.unmatched?.length ?? 0;
      const noun = total === 1 ? "entry" : "entries";
      return this.showUnmatched
        ? `Hide ${total} log ${noun}`
        : `Show ${total} log ${noun}`;
    },
  },
  methods: {
    ...mapActions(useAdminStore, ["restoreUserData"]),
    async runRestore() {
      this.isRunning = true;
      this.showUnmatched = false;
      const dryRun = this.dryRun;
      try {
        const data = await this.restoreUserData({ dryRun });
        if (data) {
          this.report = { ...data, _dryRun: dryRun };
        }
      } finally {
        this.isRunning = false;
      }
    },
    toRows(counts) {
      if (!counts) return [];
      return Object.entries(counts).sort(([a], [b]) => a.localeCompare(b));
    },
  },
};
</script>

<style scoped lang="scss">
@use "@/components/admin/tabs/admin-section.scss";

.paragraph + .paragraph {
  margin-top: 0.75em;
}

code {
  background-color: rgb(var(--v-theme-surface));
  padding: 1px 4px;
  border-radius: 3px;
  font-size: 0.85em;
}

.restoreActions {
  display: flex;
  align-items: center;
  gap: 16px;
  margin-top: 12px;
}

.restoreProgress {
  margin-top: 12px;
}

.resultSubhead {
  margin: 0 0 0.5em 0;
  font-size: 1em;
  font-weight: 500;
}

.resultSkipped {
  color: rgb(var(--v-theme-warning));
}

.resultTable {
  width: 100%;
  border-collapse: collapse;
  font-size: 0.9em;
}

.resultTable td {
  padding: 4px 0;
  border-bottom: 1px solid rgba(var(--v-border-color), var(--v-border-opacity));
}

.resultCount {
  text-align: right;
  font-variant-numeric: tabular-nums;
}

.expandToggle {
  display: flex;
  align-items: center;
  gap: 4px;
  margin-top: 8px;
  font-size: 0.85em;
  color: rgb(var(--v-theme-textSecondary));
  background: none;
  border: none;
  cursor: pointer;
  padding: 0;
}

.unmatchedLog {
  margin-top: 8px;
  padding: 8px;
  background-color: rgb(var(--v-theme-surface));
  border-radius: 4px;
  font-size: 0.8em;
  max-height: 320px;
  overflow: auto;
  white-space: pre-wrap;
  word-break: break-word;
}
</style>

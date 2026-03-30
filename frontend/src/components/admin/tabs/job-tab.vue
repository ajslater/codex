<template>
  <div id="jobs">
    <div class="jobCard">
      <div id="lastTaskLabel">Last Job Queued</div>
      <div id="lastJobResult">
        <span v-if="formSuccess" id="success">{{ formSuccess }}</span>
        <span v-else-if="formErrors && formErrors.length > 0" id="error">
          <span v-for="error in formErrors" :key="error">{{ error }}</span>
        </span>
        <span v-else id="noRecentTask">No recent job</span>
      </div>
    </div>
    <div v-for="group in ADMIN_JOBS" :key="group.title" class="jobGroup">
      <div class="groupHeader">
        <h3>{{ group.title }}</h3>
        <v-btn
          v-if="group.abort && isGroupActive(group)"
          size="small"
          color="error"
          text="Stop"
          @click="librarianTask(group.abort, 'Abort ' + group.title)"
        />
      </div>
      <!-- Select-style group (Notify) -->
      <div v-if="isSelectGroup(group.title)" class="jobCard">
        <v-select
          :items="group.jobs"
          :model-value="groupSelectValues[group.title]"
          @update:model-value="groupSelectValues[group.title] = $event"
        />
        <v-btn
          block
          :text="'Notify ' + groupSelectAttr(group.title, 'title')"
          @click="
            librarianTask(
              groupSelectValues[group.title],
              groupSelectAttr(group.title, 'title'),
            )
          "
        />
        <div class="jobDesc">
          {{ groupSelectAttr(group.title, "desc") }}
        </div>
      </div>
      <!-- Normal job rows -->
      <div v-else>
        <div
          v-for="job in group.jobs"
          :key="job.value"
          class="jobCard"
          :class="{ jobCardActive: isJobActive(job) }"
        >
          <div class="jobHeader">
            <div class="jobInfo">
              <div class="jobTitle">
                {{ job.title }}
              </div>
              <!-- Variant selector -->
              <div v-if="job.variants" class="variantRow">
                <v-select
                  class="variantSelect"
                  density="compact"
                  hide-details
                  :items="job.variants"
                  item-title="title"
                  item-value="value"
                  :model-value="selectedVariant(job)"
                  @update:model-value="variantSelections[job.value] = $event"
                />
                <div class="jobDesc">
                  {{ activeVariant(job).desc }}
                </div>
              </div>
              <!-- Simple desc for non-variant jobs -->
              <div v-else class="jobDesc">
                {{ job.desc }}
              </div>
            </div>
            <div class="jobActions">
              <span v-if="jobLastRun(job)" class="jobLastRun">
                {{ jobLastRun(job) }}
              </span>
              <ConfirmDialog
                v-if="activeConfirm(job)"
                :key="activeValue(job)"
                button-text="Start"
                :title-text="activeTitle(job)"
                :text="activeConfirm(job)"
                :block="false"
                confirm-text="Confirm"
                size="small"
                @confirm="librarianTask(activeValue(job), activeTitle(job))"
              />
              <v-btn
                v-else
                size="small"
                text="Start"
                @click="librarianTask(activeValue(job), activeTitle(job))"
              />
              <v-btn
                v-if="job.abort && isJobActive(job)"
                size="small"
                color="error"
                class="abortBtn"
                text="Stop"
                @click="librarianTask(job.abort, 'Abort ' + job.title)"
              />
            </div>
          </div>
          <!-- Expandable sub-statuses -->
          <div v-if="jobStatuses(job).length > 0" class="jobStatusSection">
            <button class="expandToggle" @click="toggleExpand(job.value)">
              <v-icon size="small">
                {{ isExpanded(job) ? mdiChevronUp : mdiChevronDown }}
              </v-icon>
              <span class="expandLabel">
                {{ jobStatusSummary(job) }}
              </span>
            </button>
            <v-expand-transition>
              <div v-if="isExpanded(job)" class="statusRows">
                <div
                  v-for="status in jobStatuses(job)"
                  :key="status.statusType"
                  class="statusRow"
                  :class="{
                    statusRowActive: status.active,
                    statusRowPreactive: !status.active && status.preactive,
                  }"
                >
                  <div class="statusHeader">
                    <span class="statusTitle">
                      {{ statusTitle(status.statusType) }}
                    </span>
                    <span
                      v-if="status.active || status.preactive"
                      class="statusTime"
                    >
                      {{ getStatusDuration(status) }}
                    </span>
                    <span v-else-if="status.updatedAt" class="statusUpdated">
                      {{ getStatusUpdatedAgo(status) }}
                    </span>
                  </div>
                  <div
                    v-if="
                      status.subtitle || hasNumbers(status) || status.active
                    "
                    class="statusDetails"
                  >
                    <span v-if="status.subtitle" class="statusSubtitle">
                      {{ status.subtitle }}
                    </span>
                    <span v-if="hasNumbers(status)" class="statusNumbers">
                      <span v-if="Number.isInteger(status.complete)">
                        {{ nf(status.complete) }} /
                      </span>
                      {{ nf(status.total) }}
                    </span>
                  </div>
                  <v-progress-linear
                    v-if="status.active || status.preactive"
                    :indeterminate="isIndeterminate(status)"
                    :model-value="statusProgress(status)"
                    :color="status.active ? 'primary' : 'grey'"
                    height="3"
                  />
                </div>
              </div>
            </v-expand-transition>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<script>
import { mdiChevronDown, mdiChevronUp } from "@mdi/js";
import { mapActions, mapState } from "pinia";

import { ADMIN_JOBS } from "@/choices/admin-jobs.json";
import {
  hasNumbers,
  isIndeterminate,
  nf,
  statusDuration,
  statusProgress,
  statusTitle,
  statusUpdatedAgo,
} from "@/components/admin/status-helpers";
import { useNowTimer } from "@/components/admin/use-now-timer";
import ConfirmDialog from "@/components/confirm-dialog.vue";
import { useAdminStore } from "@/stores/admin";
import { useCommonStore } from "@/stores/common";

const SELECT_GROUPS = Object.freeze(["Notify"]);
const NIGHTLY_JOB_VALUE = "janitor_nightly";
Object.freeze(ADMIN_JOBS);

export default {
  name: "AdminJobsTab",
  components: {
    ConfirmDialog,
  },
  setup() {
    const { now } = useNowTimer();
    return { now };
  },
  data() {
    return {
      ADMIN_JOBS,
      mdiChevronDown,
      mdiChevronUp,
      // Per-variant-job selected variant value, keyed by job.value.
      variantSelections: {},
      // Per-group select value for SELECT_GROUPS (Notify).
      groupSelectValues: {
        Notify: "notify_library_changed",
      },
      manualExpanded: {},
    };
  },
  computed: {
    ...mapState(useCommonStore, {
      formSuccess: (state) => state.form.success,
      formErrors: (state) => state.form.errors,
    }),
    ...mapState(useAdminStore, {
      allStatuses: (state) => state.allLibrarianStatuses,
    }),
    groupSelectMaps() {
      const maps = {};
      for (const group of ADMIN_JOBS) {
        if (SELECT_GROUPS.includes(group.title)) {
          maps[group.title] = {};
          for (const item of group.jobs) {
            maps[group.title][item.value] = item;
          }
        }
      }
      return maps;
    },
    isNightlyRunning() {
      /*
       * Nightly is running when start_many sets preactive on multiple
       * subtask statuses at once. Individual tasks only set active,
       * never preactive, so ≥2 preactive statuses is a reliable signal.
       */
      let preactiveCount = 0;
      for (const group of ADMIN_JOBS) {
        for (const job of group.jobs) {
          if (job.value !== NIGHTLY_JOB_VALUE) continue;
          for (const code of job.statuses || []) {
            // eslint-disable-next-line security/detect-object-injection
            const status = this.allStatuses[code];
            if (status && status.preactive !== null) {
              preactiveCount++;
              if (preactiveCount >= 2) return true;
            }
          }
        }
      }
      return false;
    },
  },
  watch: {
    allStatuses() {
      // Auto-collapse panels for jobs that are no longer active.
      for (const group of ADMIN_JOBS) {
        if (SELECT_GROUPS.includes(group.title)) continue;
        for (const job of group.jobs) {
          if (job.value in this.manualExpanded && !this.isJobActive(job)) {
            delete this.manualExpanded[job.value];
          }
        }
      }
    },
  },
  created() {
    this.loadAllStatuses();
  },
  methods: {
    ...mapActions(useAdminStore, ["librarianTask", "loadAllStatuses"]),

    // --- Variant helpers ---

    selectedVariant(job) {
      return this.variantSelections[job.value] || job.variants[0].value;
    },
    activeVariant(job) {
      if (!job.variants) {
        return job;
      }
      const selected = this.selectedVariant(job);
      return job.variants.find((v) => v.value === selected) || job.variants[0];
    },
    activeValue(job) {
      return this.activeVariant(job).value;
    },
    activeTitle(job) {
      return this.activeVariant(job).title;
    },
    activeConfirm(job) {
      return this.activeVariant(job).confirm;
    },

    // --- Group select helpers (Notify) ---

    isSelectGroup(title) {
      return SELECT_GROUPS.includes(title);
    },
    groupSelectAttr(title, attr) {
      const value = Reflect.get(this.groupSelectValues, title);
      const titleMap = Reflect.get(this.groupSelectMaps, title);
      const valueMap = Reflect.get(titleMap, value);
      return Reflect.get(valueMap, attr);
    },

    // --- Status helpers ---

    isGroupActive(group) {
      return group.jobs.some((job) => this.isJobActive(job));
    },
    jobStatuses(job) {
      if (!job.statuses || job.statuses.length === 0) {
        return [];
      }
      /*
       * Don't show nightly subtask progress unless the nightly
       * parent job itself is running.
       */
      if (job.value === NIGHTLY_JOB_VALUE && !this.isNightlyRunning) {
        return [];
      }
      const result = [];
      for (const code of job.statuses) {
        // eslint-disable-next-line security/detect-object-injection
        const status = this.allStatuses[code];
        if (status) {
          result.push(status);
        }
      }
      return result;
    },
    isJobActive(job) {
      if (job.value === NIGHTLY_JOB_VALUE) {
        return this.isNightlyRunning;
      }
      return this.jobStatuses(job).some(
        (s) => s.active !== null || s.preactive !== null,
      );
    },
    hasActiveOrPreactiveStatuses(job) {
      return this.jobStatuses(job).some(
        (s) => s.active !== null || s.preactive !== null,
      );
    },
    isExpanded(job) {
      if (job.value in this.manualExpanded) {
        return this.manualExpanded[job.value];
      }
      return this.hasActiveOrPreactiveStatuses(job);
    },
    toggleExpand(value) {
      const current =
        value in this.manualExpanded
          ? // eslint-disable-next-line security/detect-object-injection
            this.manualExpanded[value]
          : this.hasActiveOrPreactiveStatuses({ value, statuses: [] });
      // eslint-disable-next-line security/detect-object-injection
      this.manualExpanded[value] = !current;
    },
    jobStatusSummary(job) {
      const statuses = this.jobStatuses(job);
      const active = statuses.filter((s) => s.active !== null).length;
      const preactive = statuses.filter(
        (s) => s.preactive !== null && s.active === null,
      ).length;
      const total = statuses.length;
      const parts = [];
      if (active > 0) {
        parts.push(`${active} active`);
      }
      if (preactive > 0) {
        parts.push(`${preactive} pending`);
      }
      parts.push(`${total} tasks`);
      return parts.join(", ");
    },
    // --- Status helpers (delegated to status-helpers.js) ---

    statusTitle,
    hasNumbers,
    isIndeterminate,
    statusProgress,
    nf,
    getStatusDuration(status) {
      return statusDuration(status, this.now);
    },
    getStatusUpdatedAgo(status) {
      return statusUpdatedAgo(status, this.now);
    },
    jobLastRun(job) {
      if (!job.statuses || job.statuses.length === 0) {
        return "";
      }
      /*
       * Look at raw statuses (bypassing nightly gate) so we can
       * show last run time even when the job isn't active.
       */
      let latest = 0;
      for (const code of job.statuses) {
        // eslint-disable-next-line security/detect-object-injection
        const status = this.allStatuses[code];
        if (!status) continue;
        if (status.active !== null || status.preactive !== null) {
          // Job is currently running — don't show last run.
          return "";
        }
        if (status.updatedAt) {
          const t = new Date(status.updatedAt).getTime();
          if (t > latest) latest = t;
        }
      }
      if (!latest) return "";
      return statusUpdatedAgo(
        { updatedAt: new Date(latest).toISOString() },
        this.now,
      );
    },
  },
};
</script>

<style scoped lang="scss">
#jobs {
  max-width: 700px;
  margin-left: auto;
  margin-right: auto;
}

#lastTaskLabel {
  display: inline-flex;
  width: 50%;
}

#lastJobResult {
  display: inline-flex;
  width: 50%;
}

#lastJobResult * {
  width: 100%;
  text-align: right;
}

#success {
  color: rgb(var(--v-theme-success));
}

#error {
  color: rgb(var(--v-theme-error));
}

#noRecentTask {
  color: rgb(var(--v-theme-textDisabled));
}

.jobGroup {
  margin-top: 1em;
}

.groupHeader {
  display: flex;
  align-items: center;
  justify-content: space-between;
}

.jobCard {
  padding: 12px;
  margin: 8px 0;
  border-radius: 5px;
  background-color: rgb(var(--v-theme-surface-light));
  border-left: 3px solid transparent;
  transition: border-color 0.3s ease;
}

.jobCardActive {
  border-left-color: rgb(var(--v-theme-primary));
}

.jobHeader {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 12px;
}

.jobInfo {
  flex: 1;
  min-width: 0;
}

.jobTitle {
  font-weight: 500;
}

.jobLastRun {
  font-weight: normal;
  font-size: 0.8em;
  color: rgb(var(--v-theme-textDisabled));
  margin-left: 8px;
}

.jobDesc {
  color: rgb(var(--v-theme-textSecondary));
  font-size: 0.85em;
  padding-top: 2px;
}

.variantRow {
  padding-top: 4px;
}

.variantSelect {
  max-width: 320px;
}

.jobActions {
  display: flex;
  gap: 6px;
  flex-shrink: 0;
  align-items: center;
}

.abortBtn {
  margin-left: 2px;
}

.jobStatusSection {
  margin-top: 8px;
  border-top: 1px solid rgba(var(--v-theme-on-surface), 0.08);
  padding-top: 6px;
}

.expandToggle {
  display: flex;
  align-items: center;
  gap: 4px;
  background: none;
  border: none;
  color: rgb(var(--v-theme-textSecondary));
  cursor: pointer;
  font-size: 0.8em;
  padding: 2px 0;

  &:hover {
    color: rgb(var(--v-theme-textPrimary));
  }
}

.expandLabel {
  user-select: none;
}

.statusRows {
  padding-top: 4px;
}

.statusRow {
  padding: 6px 8px 6px 16px;
  margin: 2px 0;
  border-radius: 3px;
  font-size: 0.85em;
  color: rgb(var(--v-theme-textDisabled));
}

.statusRowActive {
  color: rgb(var(--v-theme-textPrimary));
  background-color: rgba(var(--v-theme-primary), 0.06);
}

.statusRowPreactive {
  color: rgb(var(--v-theme-textSecondary));
  background-color: rgba(var(--v-theme-on-surface), 0.03);
}

.statusHeader {
  display: flex;
  align-items: center;
  justify-content: space-between;
}

.statusTitle {
  font-weight: 500;
}

.statusTime {
  font-size: 0.85em;
  color: rgb(var(--v-theme-primary));
}

.statusUpdated {
  font-size: 0.8em;
  opacity: 0.6;
}

.statusDetails {
  display: flex;
  justify-content: space-between;
  padding-top: 2px;
  font-size: 0.9em;
  opacity: 0.75;
}

.statusSubtitle {
  overflow-x: auto;
  flex: 1;
  min-width: 0;
}

.statusNumbers {
  flex-shrink: 0;
  margin-left: 8px;
}
</style>

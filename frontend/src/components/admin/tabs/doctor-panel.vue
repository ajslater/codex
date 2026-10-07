<!--
  The doctor report: one row per environment check (archive backends, image
  codecs, config files, Python packages, and what codex itself needs),
  grouped by section. Opens the Stats tab, above the Platform readout it
  extends, so an admin asking "what is this install" finds what is broken
  and the command that fixes it in the same place.
-->
<template>
  <AdminSection id="doctor" title="Doctor">
    <template #actions>
      <v-btn
        size="small"
        variant="tonal"
        text="Re-check"
        :loading="checking"
        @click="recheck"
      />
    </template>
    <template #hint>
      <template v-if="doctor">
        <span v-if="headerText">{{ headerText }} · </span>
        <span
          class="doctorVerdict"
          :class="problems ? 'doctorVerdictProblems' : 'doctorVerdictOk'"
          >{{ verdict }}</span
        >
      </template>
      <template v-else>{{ CHECKING }}</template>
    </template>
    <table v-if="doctor" class="doctorTable">
      <tbody>
        <template v-for="row in rows" :key="row.key">
          <tr v-if="row.sectionStart" class="doctorSectionRow">
            <td :colspan="columns">{{ row.section }}</td>
          </tr>
          <tr class="doctorRow">
            <td class="doctorStatus">
              <v-chip
                size="small"
                variant="tonal"
                :color="statusColor(row.status)"
              >
                {{ row.status }}
              </v-chip>
            </td>
            <td class="doctorName">{{ row.name }}</td>
            <td v-if="showFound" class="doctorFound">{{ row.found }}</td>
            <td class="doctorDetail">{{ row.detail }}</td>
            <td class="doctorFix">
              <code v-if="row.fix" class="adminCode">{{ row.fix }}</code>
            </td>
          </tr>
        </template>
      </tbody>
    </table>
  </AdminSection>
</template>

<script>
import { mapActions, mapState } from "pinia";

import AdminSection from "@/components/admin/tabs/admin-section.vue";
import { useAdminStore } from "@/stores/admin";

/*
 * Every status comicbox's doctor can report, and the chip colour it wears.
 * OFF is an optional feature that is simply not set up, so it stays the
 * default grey. The failure statuses -- the ones ``problems`` counts -- are
 * all error red.
 */
export const STATUS_COLORS = Object.freeze({
  OK: "success",
  WARN: "warning",
  OFF: undefined,
  MISSING: "error",
  "WRONG VERSION": "error",
  MISCONFIGURED: "error",
  ERROR: "error",
});

export default {
  name: "AdminDoctorPanel",
  components: {
    AdminSection,
  },
  data() {
    return {
      CHECKING: "Checking…",
      NO_PROBLEMS: "No problems",
      // A Re-check is in flight. The store has no per-request flag of its
      // own and the button needs one to show the spinner.
      checking: false,
    };
  },
  computed: {
    ...mapState(useAdminStore, ["doctor"]),
    headerText() {
      return (this.doctor?.header ?? []).join(" · ");
    },
    problems() {
      return this.doctor?.problems ?? 0;
    },
    verdict() {
      if (!this.problems) return this.NO_PROBLEMS;
      return this.problems === 1 ? "1 problem" : `${this.problems} problems`;
    },
    /*
     * Report order, with a section header ahead of the first row of each
     * section. Names may repeat within a section (one WARN row per unknown
     * config key), so the row's position is the only stable key.
     */
    rows() {
      const seen = new Set();
      return (this.doctor?.results ?? []).map((result, index) => {
        const sectionStart = !seen.has(result.section);
        seen.add(result.section);
        return { ...result, key: index, sectionStart };
      });
    },
    // The admin page can be narrow; "found" is the column that gives way.
    showFound() {
      return !this.$vuetify.display.xs;
    },
    columns() {
      return this.showFound ? 5 : 4;
    },
  },
  created() {
    // A report already in the store shows at once; Re-check asks again.
    if (!this.doctor) this.loadDoctor();
  },
  methods: {
    ...mapActions(useAdminStore, ["loadDoctor"]),
    statusColor(status) {
      return Reflect.get(STATUS_COLORS, status);
    },
    async recheck() {
      this.checking = true;
      try {
        await this.loadDoctor();
      } finally {
        this.checking = false;
      }
    },
  },
};
</script>

<style scoped lang="scss">
@use "@/components/admin/tabs/admin-section.scss";
@use "@/components/admin/tabs/design.scss" as d;

.doctorVerdictOk {
  color: rgb(var(--v-theme-success));
}

.doctorVerdictProblems {
  color: rgb(var(--v-theme-error));
}

.doctorTable {
  width: 100%;
  border-collapse: collapse;
  color: rgb(var(--v-theme-text-secondary));
  font-size: d.$text-body;
  background-color: inherit;
}

.doctorTable td {
  padding: d.$space-1 d.$space-3 d.$space-1 0;
  vertical-align: top;
}

.doctorTable td:last-child {
  padding-right: 0;
}

// Alternating bands, as the key/value tables wear them.
.doctorTable tbody tr:nth-child(even) {
  background-color: rgba(var(--v-theme-on-surface), 0.05);
}

.doctorSectionRow td {
  padding-top: d.$space-3;
  font-weight: bold;
  color: rgb(var(--v-theme-text-primary));
}

.doctorStatus,
.doctorName {
  white-space: nowrap;
}

.doctorName {
  color: rgb(var(--v-theme-text-primary));
}

// Detail and fix carry the long text: a traceback fragment, a pip command.
// ``anywhere`` counts as a break opportunity when the table is sized, so a
// narrow page shrinks these columns instead of scrolling sideways.
.doctorFound,
.doctorDetail,
.doctorFix {
  overflow-wrap: anywhere;
}
</style>

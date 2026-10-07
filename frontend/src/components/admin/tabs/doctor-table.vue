<!--
  One table of doctor rows: a status chip, the check, what was found, the
  detail and the fix. With ``grouped`` a header row opens each section the
  first time it appears; without it the rows run flat under a heading the
  caller already gave them.
-->
<template>
  <table class="doctorTable">
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
</template>

<script>
/*
 * Every status the doctor can report, and the chip colour it wears.
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
  name: "AdminDoctorTable",
  props: {
    results: { type: Array, required: true },
    grouped: { type: Boolean, default: false },
  },
  computed: {
    /*
     * Report order, with a section header ahead of the first row of each
     * section when grouped. Names may repeat within a section (one WARN row
     * per unknown config key, one row per library), so the row's position
     * is the only stable key.
     */
    rows() {
      const seen = new Set();
      return this.results.map((result, index) => {
        const sectionStart = this.grouped && !seen.has(result.section);
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
  methods: {
    statusColor(status) {
      return Reflect.get(STATUS_COLORS, status);
    },
  },
};
</script>

<style scoped lang="scss">
@use "@/components/admin/tabs/admin-section.scss";
@use "@/components/admin/tabs/design.scss" as d;

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

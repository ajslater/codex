<!--
  The Doctor tab: comicbox's health report and codex's own checks, under a
  heading each. The page leads with its verdict, since that is the one thing
  an admin came to read; the host line sits under it and Re-check runs the
  report again.
-->
<template>
  <div id="doctor" class="adminReadingColumn">
    <AdminSection
      :title="verdict"
      :class="{ doctorOk: doctor && !problems, doctorProblems: problems > 0 }"
    >
      <template #actions>
        <v-btn
          size="small"
          variant="tonal"
          text="Re-check"
          :loading="checking"
          @click="recheck"
        />
      </template>
      <template v-if="headerText" #hint>{{ headerText }}</template>
      <template v-if="doctor">
        <AdminSection sub :title="COMICBOX_TITLE">
          <DoctorTable :results="doctor.comicbox" grouped />
        </AdminSection>
        <AdminSection sub :title="CODEX_TITLE">
          <DoctorTable :results="doctor.codex" />
        </AdminSection>
      </template>
    </AdminSection>
  </div>
</template>

<script>
import { mapActions, mapState } from "pinia";

import AdminSection from "@/components/admin/tabs/admin-section.vue";
import DoctorTable from "@/components/admin/tabs/doctor-table.vue";
import { useAdminStore } from "@/stores/admin";

export { STATUS_COLORS } from "@/components/admin/tabs/doctor-table.vue";

export default {
  name: "AdminDoctorTab",
  components: {
    AdminSection,
    DoctorTable,
  },
  data() {
    return {
      CHECKING: "Checking…",
      NO_PROBLEMS: "No problems",
      // The library the first rows come from, spelled the way it spells
      // itself; the second heading is this server's own checks.
      COMICBOX_TITLE: "comicbox",
      CODEX_TITLE: "Codex",
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
      if (!this.doctor) return this.CHECKING;
      if (!this.problems) return this.NO_PROBLEMS;
      return this.problems === 1 ? "1 problem" : `${this.problems} problems`;
    },
  },
  created() {
    // A report already in the store shows at once; Re-check asks again.
    if (!this.doctor) this.loadDoctor();
  },
  methods: {
    ...mapActions(useAdminStore, ["loadDoctor"]),
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

// The verdict is the heading, coloured by what it says.
.doctorOk :deep(h3) {
  color: rgb(var(--v-theme-success));
}

.doctorProblems :deep(h3) {
  color: rgb(var(--v-theme-error));
}
</style>

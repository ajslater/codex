<template>
  <v-progress-circular
    v-if="progressEnabled"
    :indeterminate="progress == null"
    :model-value="progress"
    class="progress"
    size="36"
    aria-label="`Librarian tasks in progress ${Math.round(progress)}%`"
  />
</template>

<script>
import { mapActions, mapState } from "pinia";

import { useAdminStore } from "@/stores/admin";

export default {
  name: "AdminSettingsButtonProgress",
  computed: {
    ...mapState(useAdminStore, ["librarianStatuses"]),
    progressEnabled: function () {
      return this.librarianStatuses.length > 0;
    },
    progress: function () {
      let complete = 0;
      let total = 0;
      if (!this.librarianStatuses || this.librarianStatuses.length === 0) {
        return;
      }
      for (const status of this.librarianStatuses) {
        if (
          status.total === null ||
          status.total === undefined ||
          status.complete === undefined
        ) {
          return;
        }
        complete += +status.complete;
        total += +status.total;
      }
      if (total <= 0) {
        return;
      }
      return (100 * complete) / total;
    },
  },
  created() {
    this.loadTable("LibrarianStatus");
  },
  methods: {
    ...mapActions(useAdminStore, ["loadTable"]),
  },
};
</script>

<style scoped lang="scss">
.progress {
  position: absolute;
}
</style>

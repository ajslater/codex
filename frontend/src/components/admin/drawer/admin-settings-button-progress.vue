<template>
  <v-progress-circular
    v-if="progressEnabled"
    class="progress"
    :indeterminate="!progress"
    :model-value="progress"
    aria-label="`Librarian jobs in progress ${Math.round(progress)}%`"
  />
</template>

<script>
import { mapActions, mapState } from "pinia";

import { useAdminStore } from "@/stores/admin";

export default {
  name: "AdminSettingsButtonProgress",
  computed: {
    ...mapState(useAdminStore, ["activeLibrarianStatuses"]),
    progressEnabled: function () {
      return this.activeLibrarianStatuses.length > 0;
    },
    progress: function () {
      let complete = 0;
      let total = 0;
      if (
        !this.activeLibrarianStatuses ||
        this.activeLibrarianStatuses.length === 0
      ) {
        return;
      }
      for (const status of this.activeLibrarianStatuses) {
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
    this.loadTable("ActiveLibrarianStatus");
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

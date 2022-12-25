<template>
  <span>
    <v-icon>
      {{ mdiMenu }}
    </v-icon>
    <v-progress-circular
      v-if="progressEnabled"
      :indeterminate="progress == null"
      :model-value="progress"
      class="progress"
      size="48"
      aria-label="`Librarian tasks in progress ${Math.round(progress)}%`"
    />
  </span>
</template>

<script>
import { mdiMenu } from "@mdi/js";
import { mapActions, mapState } from "pinia";

import { useAdminStore } from "@/stores/admin";

export default {
  // eslint-disable-next-line no-secrets/no-secrets
  name: "AdminSettingsDrawerButtonIcon",
  data() {
    return {
      mdiMenu,
    };
  },
  computed: {
    ...mapState(useAdminStore, {
      librarianStatuses: (state) => state.librarianStatuses,
    }),
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
  left: 0px;
  top: 0px;
}
</style>

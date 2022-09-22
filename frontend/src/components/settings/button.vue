<template>
  <v-btn v-bind="$attrs" icon ripple title="Settings" v-on="$listeners">
    <v-icon v-if="!progressEnabled">
      {{ mdiMenu }}
    </v-icon>
    <v-progress-circular
      v-else
      :indeterminate="progress == null"
      :value="progress"
      size="32"
      color="#cc7b19"
      aria-label="`Librarian tasks in progress ${Math.round(progress)}%`"
    />
  </v-btn>
</template>

<script>
import { mdiMenu } from "@mdi/js";
import { mapActions, mapState } from "pinia";

import { useAdminStore } from "@/stores/admin";

export default {
  name: "SettingsDrawerButton",
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
      if (this.librarianStatuses.length === 0) {
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

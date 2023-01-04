<template>
  <v-divider v-if="show" />
  <v-list-item @click="load">
    <v-expand-transition>
      <div v-if="show">
        <CloseButton
          id="clearButton"
          title="Clear Librarian Statuses"
          size="small"
          @click="clear"
        />
        <h4>Librarian Tasks</h4>
        <v-expand-transition
          v-for="status of librarianStatuses"
          :key="`${status.type} ${status.name}`"
        >
          <div nav class="statusItem">
            <div class="statusItemTitle">
              {{ status.type }} {{ status.name }}
              <span v-if="+status.total">
                {{ status.complete }}/{{ status.total }}
              </span>
            </div>
            <v-progress-linear
              :indeterminate="indeterminate(status)"
              :model-value="progress(status)"
              bottom
            />
          </div>
        </v-expand-transition>
      </div>
      <v-list-item-title v-else id="noTasksRunning">
        No librarian tasks running
      </v-list-item-title>
    </v-expand-transition>
  </v-list-item>
</template>

<script>
import { mdiCloseCircleOutline } from "@mdi/js";
import { mapActions, mapState } from "pinia";

import CloseButton from "@/components/close-button.vue";
import { useAdminStore } from "@/stores/admin";

export default {
  name: "AdminStatusList",
  components: {
    CloseButton,
  },
  data() {
    return { mdiCloseCircleOutline };
  },
  computed: {
    ...mapState(useAdminStore, {
      librarianStatuses: (state) => state.librarianStatuses,
      show: (state) => state.librarianStatuses.length > 0,
    }),
  },
  created() {
    this.load();
  },
  methods: {
    ...mapActions(useAdminStore, ["loadTable", "librarianTask"]),
    indeterminate: (status) => !status.preactive && +status.total === 0,
    progress(status) {
      if (status.preactive || +status.total === 0) {
        return 0;
      }
      return (100 * +status.complete) / +status.total;
    },
    load() {
      this.loadTable("LibrarianStatus");
    },
    clear() {
      this.librarianTask("librarian_clear_status", "");
    },
  },
};
</script>

<style scoped lang="scss">
h4 {
  padding-top: 10px;
  padding-left: 16px;
  padding-right: 10px;
  padding-bottom: 10px;
}
.statusItem {
  padding-left: 16px;
  padding-right: 5px;
  padding-bottom: 10px;
  color: rgb(var(--v-theme-textDisabled));
}
#noTasksRunning {
  margin-left: 1em;
  color: rgb(var(--v-theme-textDisabled));
}
#clearButton {
  float: right;
}
</style>

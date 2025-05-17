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
          :key="status.statusType"
        >
          <StatusListItem status="status" />
        </v-expand-transition>
      </div>
      <v-list-item-title v-else id="noTasksRunning">
        No librarian tasks running
      </v-list-item-title>
    </v-expand-transition>
  </v-list-item>
</template>

<script>
import { mapActions, mapState } from "pinia";

import CloseButton from "@/components/close-button.vue";
import StatusListItem from "@/components/admin/drawer/status-list-item.vue";
import { useAdminStore } from "@/stores/admin";

export default {
  name: "AdminStatusList",
  components: {
    CloseButton,
    StatusListItem,
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

#noTasksRunning {
  margin-left: 1em;
  color: rgb(var(--v-theme-textDisabled));
}

#clearButton {
  float: right;
}
</style>

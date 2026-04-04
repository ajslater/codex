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
        <div class="settingsHeader">Librarian Tasks</div>
        <v-expand-transition
          v-for="status of activeLibrarianStatuses"
          :key="status.id"
        >
          <StatusListItem :status="status" :now="now" />
        </v-expand-transition>
      </div>
      <v-list-item-title v-else id="noTasksRunning">
        No librarian jobs running
      </v-list-item-title>
    </v-expand-transition>
  </v-list-item>
</template>

<script>
import { mapActions, mapState } from "pinia";

import StatusListItem from "@/components/admin/drawer/status-list-item.vue";
import { useNowTimer } from "@/components/admin/use-now-timer";
import CloseButton from "@/components/close-button.vue";
import { useAdminStore } from "@/stores/admin";

export default {
  name: "AdminStatusList",
  components: {
    CloseButton,
    StatusListItem,
  },
  setup() {
    const { now } = useNowTimer();
    return { now };
  },
  computed: {
    ...mapState(useAdminStore, {
      activeLibrarianStatuses: (state) => state.activeLibrarianStatuses,
      show: (state) => state.activeLibrarianStatuses.length > 0,
    }),
  },
  created() {
    this.load();
  },
  methods: {
    ...mapActions(useAdminStore, ["loadTable", "librarianTask"]),
    load() {
      this.loadTable("ActiveLibrarianStatus");
    },
    clear() {
      this.librarianTask("librarian_clear_status", "");
    },
  },
};
</script>

<style scoped lang="scss">
.settingsHeader {
  padding-top: 10px;
  padding-left: 0px;
  padding-right: 0px;
  padding-bottom: 10px;
  font-weight: bolder;
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

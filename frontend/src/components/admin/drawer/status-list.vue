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
          :key="status.id"
        >
          <StatusListItem :status="status" :now="now" />
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

import StatusListItem from "@/components/admin/drawer/status-list-item.vue";
import CloseButton from "@/components/close-button.vue";
import { useAdminStore } from "@/stores/admin";
import { useCommonStore } from "@/stores/common";

export default {
  name: "AdminStatusList",
  components: {
    CloseButton,
    StatusListItem,
  },
  data() {
    return { now: Date.now() };
  },
  computed: {
    ...mapState(useCommonStore, {
      isSettingsDrawerOpen: (state) => state.isSettingsDrawerOpen,
    }),
    ...mapState(useAdminStore, {
      librarianStatuses: (state) => state.librarianStatuses,
      show: (state) => state.librarianStatuses.length > 0,
    }),
  },
  created() {
    this.load();
  },
  watch: {
    show(to) {
      if (to) {
        this.updateTime();
      }
    },
    isSettingsDrawerOpen(to) {
      if (to) {
        this.updateTime();
      }
    },
  },
  mounted() {
    this.updateTime();
  },
  methods: {
    ...mapActions(useAdminStore, ["loadTable", "librarianTask"]),
    load() {
      this.loadTable("LibrarianStatus");
    },
    clear() {
      this.librarianTask("librarian_clear_status", "");
    },
    updateTime() {
      this.now = Date.now();
      setTimeout(() => {
        if (this.isSettingsDrawerOpen && this.show) {
          this.updateTime();
        }
      }, 1000);
    },
  },
};
</script>

<style scoped lang="scss">
h4 {
  padding-top: 10px;
  padding-left: 0px;
  padding-right: 0px;
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

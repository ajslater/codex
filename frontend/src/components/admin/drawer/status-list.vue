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
          <div nav class="statusItem">
            <div class="statusItemTitle">
              {{ title(status) }}
              <div v-if="status.subtitle" class="statusItemSubtitle">
                {{ status.subtitle }}
              </div>
              <div
                v-if="showComplete(status) || Number.isInteger(status.total)"
                class="statusItemSubtitle"
              >
                <span v-if="showComplete(status)">
                  {{ nf(status.complete) }} /
                </span>
                {{ nf(status.total) }}
              </div>
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

import STATUS_TITLES from "@/choices/admin-status-titles.json";
import CloseButton from "@/components/close-button.vue";
import { NUMBER_FORMAT } from "@/datetime";
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
    showComplete: (status) => Number.isInteger(status.complete),
    indeterminate: (status) =>
      !status.preactive &&
      (!status.total || !Number.isInteger(status.complete)),
    progress(status) {
      if (status.preactive || self.indeterminate) {
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
    title(status) {
      return STATUS_TITLES[status.statusType];
    },
    nf(val) {
      return Number.isInteger(val) ? NUMBER_FORMAT.format(val) : "?";
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
.statusItemSubtitle {
  padding-left: 1rem;
  opacity: 0.75;
}
#noTasksRunning {
  margin-left: 1em;
  color: rgb(var(--v-theme-textDisabled));
}
#clearButton {
  float: right;
}
</style>

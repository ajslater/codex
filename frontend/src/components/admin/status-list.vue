<template>
  <v-list-item-group>
    <v-divider v-if="show" />
    <v-list-item ripple @click="load">
      <v-list-item-content>
        <v-expand-transition>
          <div v-if="show">
            <v-btn
              id="clearButton"
              small
              ripple
              icon
              title="Clear Librarian Statuses"
              @click="clear"
              ><v-icon>{{ mdiCloseCircleOutline }}</v-icon></v-btn
            >
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
                  color="#cc7b19"
                  :indeterminate="!status.preactive && +status.total === 0"
                  :value="computeValue(status)"
                  bottom
                />
              </div>
            </v-expand-transition>
          </div>
          <v-list-item-title v-else id="noTasksRunning">
            No librarian tasks running
          </v-list-item-title>
        </v-expand-transition>
      </v-list-item-content>
    </v-list-item>
  </v-list-item-group>
</template>

<script>
import { mdiCloseCircleOutline } from "@mdi/js";
import { mapActions, mapState } from "pinia";

import { useAdminStore } from "@/stores/admin";

export default {
  name: "AdminStatusList",
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
    computeValue: function (status) {
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
  paddint-bottom: 10px;
}
.statusItem {
  padding-left: 16px;
  padding-right: 5px;
  padding-bottom: 10px;
  color: gray;
}
#noTasksRunning {
  margin-left: 1em;
  color: grey;
}
#clearButton {
  float: right;
  color: grey;
}
</style>

<template>
  <v-list-item-group>
    <v-list-item ripple @click="load">
      <v-list-item-content>
        <v-expand-transition>
          <div v-if="librarianStatuses.length > 0">
            <v-divider />
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
import { mapActions, mapState } from "pinia";

import { useAdminStore } from "@/stores/admin";

export default {
  name: "AdminStatusList",
  computed: {
    ...mapState(useAdminStore, {
      librarianStatuses: (state) => state.librarianStatuses,
    }),
  },
  created() {
    this.load();
  },
  methods: {
    ...mapActions(useAdminStore, ["loadTable"]),
    computeValue: function (status) {
      if (status.preactive || +status.total === 0) {
        return 0;
      }
      return (100 * +status.complete) / +status.total;
    },
    load() {
      this.loadTable("LibrarianStatus");
    },
  },
};
</script>

<style scoped lang="scss">
h4 {
  padding-top: 10px;
  padding-left: 16px;
  padding-right: 10px;
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
</style>

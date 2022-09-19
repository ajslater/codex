<template>
  <div v-if="isUserAdmin">
    <v-divider />
    <h3 id="adminMenuTitle">Admin Tools</h3>
    <v-list-item-group>
      <v-list-item ripple @click="librarianTask('poll')">
        <v-list-item-content>
          <v-list-item-title>Poll All Libraries</v-list-item-title>
        </v-list-item-content>
      </v-list-item>
      <v-list-item
        :to="{ name: 'admin' }"
        ripple
        @click="unseedFailedImports = false"
      >
        <v-list-item-content>
          <v-list-item-title>
            Admin Panel
            <v-icon
              v-if="unseenFailedImports"
              id="failedImportsIcon"
              title="New Failed Imports"
            >
              {{ mdiBookAlert }}
            </v-icon>
          </v-list-item-title>
        </v-list-item-content>
      </v-list-item>
    </v-list-item-group>
    <AdminStatusList />
  </div>
</template>

<script>
import { mdiBookAlert, mdiOpenInNew } from "@mdi/js";
import { mapActions, mapGetters, mapWritableState } from "pinia";

import AdminStatusList from "@/components/admin/status-list.vue";
import { useAdminStore } from "@/stores/admin";
import { useAuthStore } from "@/stores/auth";

export default {
  name: "AdminMenu",
  components: {
    AdminStatusList,
  },
  data() {
    return {
      mdiBookAlert,
      mdiOpenInNew,
    };
  },
  computed: {
    ...mapGetters(useAuthStore, ["isUserAdmin"]),
    ...mapWritableState(useAdminStore, {
      unseenFailedImports: (state) => state.unseenFailedImports,
    }),
  },
  methods: {
    ...mapActions(useAdminStore, ["clearFailedImports", "librarianTask"]),
  },
};
</script>

<style scoped lang="scss">
#adminMenuTitle {
  padding-top: 10px;
  padding-left: 15px;
}
#failedImportsIcon {
  padding-left: 10px;
}
</style>

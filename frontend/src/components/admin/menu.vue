<template>
  <div v-if="isUserAdmin">
    <v-divider />
    <h3 id="adminMenuTitle">Admin Tools</h3>
    <v-list-item-group>
      <v-list-item ripple @click="poll">
        <v-list-item-content>
          <v-list-item-title>Poll All Libraries</v-list-item-title>
        </v-list-item-content>
      </v-list-item>
      <v-list-item
        :href="adminURL"
        target="_blank"
        ripple
        @click="setFailedImports(false)"
      >
        <v-list-item-content>
          <v-list-item-title
            >Admin Panel
            <v-icon id="adminPanelOpenIcon">{{ mdiOpenInNew }}</v-icon>
            <v-icon
              v-if="failedImports"
              id="failedImportsIcon"
              title="New Failed Imports"
              >{{ mdiBookAlert }}</v-icon
            >
          </v-list-item-title>
        </v-list-item-content>
      </v-list-item>
    </v-list-item-group>
    <AdminStatusList />
  </div>
</template>

<script>
import { mdiBookAlert, mdiOpenInNew } from "@mdi/js";
import { mapActions, mapGetters, mapState } from "pinia";

import API from "@/api/v3/admin.js";
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
      adminURL: window.CODEX.ADMIN_PATH,
      mdiBookAlert,
      mdiOpenInNew,
    };
  },
  computed: {
    ...mapGetters(useAuthStore, ["isUserAdmin"]),
    ...mapState(useAdminStore, {
      failedImports: (state) => state.failedImports,
    }),
  },
  methods: {
    ...mapActions(useAdminStore, ["setFailedImports"]),
    poll: function () {
      API.queueJob("poll");
    },
  },
};
</script>

<style scoped lang="scss">
#adminMenuTitle {
  padding-top: 10px;
  padding-left: 15px;
}
#adminPanelOpenIcon,
#failedImportsIcon {
  color: gray !important;
}
#failedImportsIcon {
  padding-left: 10px;
}
</style>

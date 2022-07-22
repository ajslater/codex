<template>
  <div v-if="isAdmin">
    <v-divider />
    <h3 id="adminMenuTitle">Admin Tools</h3>
    <v-list-item-group>
      <v-list-item ripple @click="poll">
        <v-list-item-content>
          <v-list-item-title>Poll All Libraries</v-list-item-title>
        </v-list-item-content>
      </v-list-item>
      <v-list-item :href="adminURL" target="_blank" ripple>
        <v-list-item-content>
          <v-list-item-title
            >Admin Panel
            <v-icon id="adminPanelIcon">{{
              mdiOpenInNew
            }}</v-icon></v-list-item-title
          >
        </v-list-item-content>
      </v-list-item>
      <v-list-item
        v-if="failedImports.length > 0"
        :href="`${adminURL}codex/failedimport/`"
        target="_blank"
        ripple
      >
        <v-list-item-content>
          <v-list-item-title>
            {{ failedImports.length }} failed imports
            <v-icon id="adminPanelIcon">{{ mdiOpenInNew }}</v-icon>
          </v-list-item-title>
        </v-list-item-content>
      </v-list-item>
    </v-list-item-group>
    <AdminStatusList />
  </div>
</template>

<script>
import { mdiOpenInNew } from "@mdi/js";
import { mapActions, mapGetters, mapState } from "vuex";

import API from "@/api/v2/admin";
import AdminStatusList from "@/components/admin-status-list";

export default {
  name: "AdminMenu",
  components: {
    AdminStatusList,
  },
  data() {
    return {
      adminURL: API.ADMIN_URL,
      mdiOpenInNew,
    };
  },
  computed: {
    ...mapGetters("auth", ["isAdmin"]),
    ...mapState("admin", { failedImports: (state) => state.failedImports }),
  },
  created() {
    this.fetchFailedImports();
  },
  methods: {
    poll: function () {
      API.queueJob("poll");
    },
    ...mapActions("admin", ["fetchFailedImports"]),
  },
};
</script>

<style scoped lang="scss">
#adminMenuTitle {
  padding-top: 10px;
  padding-left: 15px;
}
#adminPanelIcon {
  color: gray;
}
</style>

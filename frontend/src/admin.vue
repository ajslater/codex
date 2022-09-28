<template>
  <div id="adminWrapper">
    <div v-if="isUserAdmin" id="adminContainer">
      <v-main>
        <AdminTitleToolbar />
        <AdminTabs />
      </v-main>
      <AdminSettingsDrawer ref="settingsDrawer" />
    </div>
    <div v-else id="announcement">
      <h1>
        <router-link :to="{ name: 'home' }"> Log in </router-link>
        as an Administrator to use this panel
      </h1>
    </div>
  </div>
</template>

<script>
import { mapGetters } from "pinia";

import AdminSettingsDrawer from "@/components/admin/admin-settings-drawer.vue";
import AdminTitleToolbar from "@/components/admin/admin-title-toolbar.vue";
import AdminTabs from "@/components/admin/tabs.vue";
import { useAuthStore } from "@/stores/auth";

export default {
  name: "MainAdmin",
  components: {
    AdminTitleToolbar,
    AdminTabs,
    AdminSettingsDrawer,
  },
  computed: {
    ...mapGetters(useAuthStore, ["isUserAdmin"]),
  },
};
</script>

<style scoped lang="scss">
#adminContainer {
  padding-bottom: env(safe-area-inset-bottom);
}
#announcement {
  position: absolute;
  top: 50%;
  left: 50%;
  transform: translateX(-50%) translateY(-50%);
}
</style>

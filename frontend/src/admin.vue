<template>
  <div id="adminWrapper">
    <div v-if="isUserAdmin" id="adminContainer">
      <v-main>
        <AdminTitleToolbar />
        <AdminTabs />
      </v-main>
      <SettingsDrawer
        title="Admin Status"
        :admin="true"
        :panel="AdminSettingsPanel"
      />
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
import { markRaw } from "vue";

import AdminSettingsPanel from "@/components/admin/admin-settings-panel.vue";
import AdminTitleToolbar from "@/components/admin/admin-title-toolbar.vue";
import AdminTabs from "@/components/admin/tabs.vue";
import SettingsDrawer from "@/components/settings/settings-drawer.vue";
import { useAuthStore } from "@/stores/auth";

export default {
  name: "MainAdmin",
  components: {
    AdminTitleToolbar,
    AdminTabs,
    SettingsDrawer,
  },
  data() {
    return {
      AdminSettingsPanel: markRaw(AdminSettingsPanel),
    };
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

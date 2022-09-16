<template>
  <div id="adminWrapper">
    <div v-if="isUserAdmin" id="adminContainer">
      <v-main>
        <v-toolbar dense>
          <v-spacer />
          <v-toolbar-title>Codex Administration</v-toolbar-title>
          <v-spacer />
          <SettingsDrawerButton
            :class="{ invisible: isSettingsDrawerOpen }"
            :disabled="isSettingsDrawerOpen"
            :plain="isSettingsDrawerOpen"
            @click="isSettingsDrawerOpen = true"
          />
        </v-toolbar>
        <AdminTabs />
      </v-main>
      <AdminSettingsDrawer ref="settingsDrawer" />
    </div>
    <div v-else id="announcement">
      <h1>
        <router-link :to="{ name: 'home' }">Log in</router-link> as an
        Administrator to use this panel
      </h1>
    </div>
  </div>
</template>

<script>
import { mdiOpenInNew } from "@mdi/js";
import { mapGetters, mapWritableState } from "pinia";

import AdminSettingsDrawer from "@/components/admin/settings-drawer.vue";
import AdminTabs from "@/components/admin/tabs.vue";
import SettingsDrawerButton from "@/components/settings/button.vue";
import { useAdminStore } from "@/stores/admin";
import { useAuthStore } from "@/stores/auth";

export default {
  name: "MainAdmin",
  components: {
    AdminTabs,
    AdminSettingsDrawer,
    SettingsDrawerButton,
  },
  data() {
    return {
      djangoAdminURL: window.CODEX.ADMIN_PATH,
      mdiOpenInNew,
    };
  },
  computed: {
    ...mapGetters(useAuthStore, ["isUserAdmin"]),
    ...mapWritableState(useAdminStore, ["isSettingsDrawerOpen"]),
  },
  created() {
    this.isSettingsDrawerOpen = !this.$vuetify.breakpoint.mobile;
  },
};
</script>

<style scoped lang="scss">
#adminContainer {
  max-width: 100%;
  position: relative;
}
#announcement {
  position: absolute;
  top: 50%;
  left: 50%;
  transform: translateX(-50%) translateY(-50%);
}
.invisible {
  visibility: hidden;
}
@import "./components/anchors.scss";
</style>

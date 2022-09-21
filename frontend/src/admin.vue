<template>
  <div id="adminWrapper">
    <div v-if="isUserAdmin" id="adminContainer">
      <v-main>
        <v-toolbar id="titleBar" dense>
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
        <router-link :to="{ name: 'home' }"> Log in </router-link>
        as an Administrator to use this panel
      </h1>
    </div>
  </div>
</template>

<script>
import { mdiOpenInNew } from "@mdi/js";
import { mapGetters, mapWritableState } from "pinia";

import AdminSettingsDrawer from "@/components/admin/admin-settings-drawer.vue";
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
      mdiOpenInNew,
    };
  },
  computed: {
    ...mapGetters(useAuthStore, ["isUserAdmin"]),
    ...mapWritableState(useAdminStore, ["isSettingsDrawerOpen"]),
  },
  mounted() {
    this.isSettingsDrawerOpen = !this.$vuetify.breakpoint.mobile;
  },
};
</script>

<style scoped lang="scss">
#adminContainer {
  max-width: 100%;
  position: relative;
  padding-bottom: env(safe-area-inset-bottom);
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
#titleBar {
  position: fixed;
  width: 100%;
  top: 0px;
  z-index: 10;
  padding-top: env(safe-area-inset-top);
  padding-right: calc(env(safe-area-inset-right) / 3);
  padding-left: calc(env(safe-area-inset-left) / 3);
}
@import "./components/anchors.scss";
</style>

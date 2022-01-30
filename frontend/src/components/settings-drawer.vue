<template>
  <v-navigation-drawer
    id="settingsDrawer"
    v-model="isSettingsDrawerOpen"
    app
    right
    temporary
  >
    <v-list dense>
      <BrowserSettingsPanel v-if="isOpenToSee && $route.name === 'browser'" />
      <ReaderSettingsPanel v-if="isOpenToSee && $route.name === 'reader'" />
      <v-divider />
      <AuthLoginDialog />
      <VersionsFooter />
    </v-list>
  </v-navigation-drawer>
</template>

<script>
import { mapGetters } from "vuex";

import AuthLoginDialog from "@/components/auth-login-dialog";
import BrowserSettingsPanel from "@/components/browser-settings-panel";
import ReaderSettingsPanel from "@/components/reader-settings-panel";
import VersionsFooter from "@/components/version-footer";

export default {
  name: "SettingsDrawer",
  components: {
    AuthLoginDialog,
    BrowserSettingsPanel,
    ReaderSettingsPanel,
    VersionsFooter,
  },
  computed: {
    ...mapGetters("auth", ["isLoggedIn", "isOpenToSee"]),
    isSettingsDrawerOpen: {
      get() {
        return this.$store.state.isSettingsDrawerOpen;
      },
      set(value) {
        this.$store.commit("setIsSettingsDrawerOpen", value);
      },
    },
  },
};
</script>

<style scoped lang="scss">
#settingsDrawer {
  background-color: #121212;
  z-index: 20;
}
</style>

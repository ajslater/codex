<template>
  <v-navigation-drawer
    id="settingsDrawer"
    v-model="settingsDrawerOpen"
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
import { mapGetters, mapMutations, mapState } from "vuex";

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
    ...mapState({
      isSettingsDrawerOpen: (state) => state.isSettingsDrawerOpen,
    }),
    settingsDrawerOpen: {
      get() {
        return this.isSettingsDrawerOpen;
      },
      set(value) {
        this.setIsSettingsDrawerOpen(value);
      },
    },
  },
  methods: {
    ...mapMutations(["setIsSettingsDrawerOpen"]),
  },
};
</script>

<style scoped lang="scss">
#settingsDrawer {
  background-color: #121212;
  z-index: 20;
}
</style>

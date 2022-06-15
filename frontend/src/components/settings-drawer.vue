<template>
  <v-navigation-drawer
    id="settingsDrawer"
    v-model="settingsDrawerOpen"
    app
    right
    temporary
  >
    <v-list dense>
      <component
        :is="panel"
        v-if="isOpenToSee"
        ref="panel"
        @panelMounted="panelMounted"
      />
      <v-divider />
      <AdminMenu />
      <v-divider />
      <AuthLoginDialog />
      <VersionsFooter />
    </v-list>
  </v-navigation-drawer>
</template>

<script>
import { mapGetters } from "vuex";

import AdminMenu from "@/components/admin-menu";
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
    AdminMenu,
  },
  props: {
    panel: { type: Object, required: true },
  },
  data() {
    return {
      panelReady: false,
    };
  },
  computed: {
    ...mapGetters("auth", ["isLoggedIn", "isOpenToSee"]),
    settingsDrawerOpen: {
      get() {
        return this.panelReady && this.$refs["panel"]
          ? this.$refs["panel"].isSettingsDrawerOpen
          : false;
      },
      set(value) {
        this.$refs["panel"].setIsSettingsDrawerOpen(value);
      },
    },
  },
  methods: {
    panelMounted: function () {
      this.panelReady = true;
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

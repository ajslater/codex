<template>
  <v-main v-if="isAuthorized" id="browser">
    <BrowserHeadToolbars />
    <BrowserMain />
    <BrowserNavToolbar />
    <BrowserSettingsDrawer />
  </v-main>
  <Unauthorized v-else />
</template>

<script>
import { mapActions, mapGetters, mapState } from "pinia";

import BrowserSettingsDrawer from "@/components/browser/drawer/browser-settings-drawer.vue";
import BrowserMain from "@/components/browser/main.vue";
import BrowserHeadToolbars from "@/components/browser/toolbars/browser-toolbars-head.vue";
import BrowserNavToolbar from "@/components/browser/toolbars/nav/browser-toolbar-nav.vue";
import Unauthorized from "@/components/unauthorized.vue";
import { useAuthStore } from "@/stores/auth";
import { useBrowserStore } from "@/stores/browser";

export default {
  name: "MainBrowser",
  components: {
    BrowserHeadToolbars,
    BrowserMain,
    BrowserNavToolbar,
    BrowserSettingsDrawer,
    Unauthorized,
  },
  computed: {
    ...mapState(useAuthStore, {
      user: (state) => state.user,
    }),
    ...mapGetters(useAuthStore, ["isAuthorized"]),
  },
  watch: {
    $route: function () {
      window.scrollTo(0, 0);
      this.loadBrowserPage();
    },
    user: function () {
      this.loadSettings();
    },
    isAuthorized: function () {
      this.loadSettings();
    },
  },
  created() {
    this.loadSettings();
  },
  methods: {
    ...mapActions(useBrowserStore, ["loadBrowserPage", "loadSettings"]),
  },
};
</script>

<style scoped lang="scss">
#browser {
  display: flex;
  flex-direction: column;
  min-height: 100vh;
}
</style>

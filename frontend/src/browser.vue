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
    $route(to) {
      window.scrollTo(0, 0);
      this.setPageMtime(to?.query?.ts);
      this.loadBrowserPage();
    },
    user() {
      this.loadSettings();
    },
    isAuthorized() {
      this.loadSettings();
    },
  },
  created() {
    this.loadSettings();
  },
  methods: {
    ...mapActions(useBrowserStore, [
      "loadBrowserPage",
      "loadSettings",
      "setPageMtime",
    ]),
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

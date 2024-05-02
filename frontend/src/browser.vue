<template>
  <v-main v-if="isCodexViewable" id="browser">
    <header class="codexToolbar">
      <BrowserTopToolbar />
      <BrowserTitleToolbar />
    </header>
    <BrowserMain />
    <BrowserNavToolbar />
  </v-main>
  <Unauthorized v-else />
  <BrowserSettingsDrawer />
</template>

<script>
import { mapActions, mapGetters, mapState } from "pinia";

import BrowserSettingsDrawer from "@/components/browser/drawer/browser-settings-drawer.vue";
import BrowserMain from "@/components/browser/main.vue";
import BrowserNavToolbar from "@/components/browser/toolbars/nav/browser-nav-toolbar.vue";
import BrowserTitleToolbar from "@/components/browser/toolbars/title/browser-title-toolbar.vue";
import BrowserTopToolbar from "@/components/browser/toolbars/top/browser-top-toolbar.vue";
import Unauthorized from "@/components/unauthorized.vue";
import { useAuthStore } from "@/stores/auth";
import { useBrowserStore } from "@/stores/browser";

export default {
  name: "MainBrowser",
  components: {
    BrowserTopToolbar,
    BrowserMain,
    BrowserNavToolbar,
    BrowserTitleToolbar,
    BrowserSettingsDrawer,
    Unauthorized,
  },
  computed: {
    ...mapState(useAuthStore, {
      user: (state) => state.user,
    }),
    ...mapGetters(useAuthStore, ["isCodexViewable"]),
  },
  watch: {
    $route: function () {
      window.scrollTo(0, 0);
      this.loadBrowserPage();
    },
    user: function () {
      this.loadSettings();
    },
    isCodexViewable: function () {
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
      "getVersions",
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
.codexToolbar {
  z-index: 100;
}
</style>

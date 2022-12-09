<template>
  <v-main id="browser">
    <header class="codexToolbar">
      <BrowserFilterToolbar />
      <BrowserTitleToolbar />
    </header>
    <BrowserMain />
    <BrowserNavToolbar />
  </v-main>
  <SettingsDrawer
    title="Browser Settings"
    :panel="BrowserSettingsPanel"
    temporary
  />
</template>

<script>
import { mapActions, mapGetters, mapState } from "pinia";
import { markRaw } from "vue";

import BrowserNavToolbar from "@/components/browser/browser-nav-toolbar.vue";
import BrowserSettingsPanel from "@/components/browser/browser-settings-panel.vue";
import BrowserTitleToolbar from "@/components/browser/browser-title-toolbar.vue";
import BrowserFilterToolbar from "@/components/browser/filter-toolbar.vue";
import BrowserMain from "@/components/browser/main.vue";
import SettingsDrawer from "@/components/settings/settings-drawer.vue";
import { useAuthStore } from "@/stores/auth";
import { useBrowserStore } from "@/stores/browser";
import { useCommonStore } from "@/stores/common";

export default {
  name: "MainBrowser",
  components: {
    BrowserFilterToolbar,
    BrowserMain,
    BrowserNavToolbar,
    BrowserTitleToolbar,
    SettingsDrawer,
  },
  data() {
    return {
      BrowserSettingsPanel: markRaw(BrowserSettingsPanel),
    };
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
    // mapWritableState does not work.
    useCommonStore().isSettingsDrawerOpen = false;
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

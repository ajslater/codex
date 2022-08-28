<template>
  <div id="browser">
    <header id="browserHeader">
      <BrowserFilterToolbar />
      <BrowserTitleToolbar />
    </header>
    <BrowserMain />
    <BrowserPaginationToolbar />
    <BrowserSettingsDrawer />
  </div>
</template>

<script>
import { mapActions, mapGetters, mapState } from "pinia";

import BrowserFilterToolbar from "@/components/browser-filter-toolbar.vue";
import BrowserMain from "@/components/browser-main.vue";
import BrowserPaginationToolbar from "@/components/browser-pagination-toolbar.vue";
import BrowserSettingsDrawer from "@/components/browser-settings-drawer.vue";
import BrowserTitleToolbar from "@/components/browser-title-toolbar.vue";
import { useAuthStore } from "@/stores/auth";
import { useBrowserStore } from "@/stores/browser";

export default {
  name: "MainBrowser",
  components: {
    BrowserFilterToolbar,
    BrowserMain,
    BrowserPaginationToolbar,
    BrowserTitleToolbar,
    BrowserSettingsDrawer,
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
#browserHeader {
  position: fixed;
  z-index: 10;
}
</style>

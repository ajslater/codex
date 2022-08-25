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
import { mapActions, mapGetters, mapState } from "vuex";

import BrowserFilterToolbar from "@/components/browser-filter-toolbar.vue";
import BrowserMain from "@/components/browser-main.vue";
import BrowserPaginationToolbar from "@/components/browser-pagination-toolbar.vue";
import BrowserSettingsDrawer from "@/components/browser-settings-drawer.vue";
import BrowserTitleToolbar from "@/components/browser-title-toolbar.vue";

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
    ...mapState("auth", {
      user: (state) => state.user,
    }),
    ...mapGetters("auth", ["isOpenToSee"]),
  },
  watch: {
    $route: function () {
      window.scrollTo(0, 0);
      this.getBrowserPage();
    },
    user: function () {
      this.loadSettings();
      this.getVersions();
    },
    isOpenToSee: function () {
      this.loadSettings();
      this.getVersions();
    },
  },
  created() {
    this.loadSettings();
    this.getVersions();
  },
  methods: {
    ...mapActions("browser", ["getBrowserPage", "loadSettings", "getVersions"]),
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

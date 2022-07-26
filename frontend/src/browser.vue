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

import BrowserFilterToolbar from "@/components/browser-filter-toolbar";
import BrowserMain from "@/components/browser-main";
import BrowserPaginationToolbar from "@/components/browser-pagination-toolbar";
import BrowserSettingsDrawer from "@/components/browser-settings-drawer";
import BrowserTitleToolbar from "@/components/browser-title-toolbar";

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
      this.getBrowserPage();
    },
    user: function () {
      this.browserOpened();
    },
    isOpenToSee: function () {
      this.browserOpened();
    },
  },
  created() {
    this.browserOpened();
  },
  methods: {
    ...mapActions("browser", ["getBrowserPage", "browserOpened"]),
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

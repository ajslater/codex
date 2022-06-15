<template>
  <div id="browser">
    <header id="browserHeader">
      <BrowserFilterToolbar />
      <BrowserTitleToolbar />
    </header>
    <BrowserMain />
    <BrowserPaginationToolbar />
    <SettingsDrawer :panel="panel" />
  </div>
</template>

<script>
import { mapActions, mapGetters, mapState } from "vuex";

import BrowserFilterToolbar from "@/components/browser-filter-toolbar";
import BrowserMain from "@/components/browser-main";
import BrowserPaginationToolbar from "@/components/browser-pagination-toolbar";
import BrowserSettingsPanel from "@/components/browser-settings-panel";
import BrowserTitleToolbar from "@/components/browser-title-toolbar";
import SettingsDrawer from "@/components/settings-drawer";

export default {
  name: "MainBrowser",
  components: {
    BrowserFilterToolbar,
    BrowserMain,
    BrowserPaginationToolbar,
    BrowserTitleToolbar,
    SettingsDrawer,
  },
  data() {
    return {
      panel: BrowserSettingsPanel,
    };
  },
  computed: {
    ...mapState("auth", {
      user: (state) => state.user,
    }),
    ...mapGetters("auth", ["isOpenToSee"]),
  },
  watch: {
    $route: function () {
      if (this.isOpenToSee) {
        this.browserPageStale();
      }
    },
    user: function () {
      this.opened();
    },
    isOpenToSee: function () {
      this.opened();
    },
  },
  created() {
    this.opened();
  },
  methods: {
    ...mapActions("browser", ["browserPageStale", "browserOpened"]),
    opened: function () {
      if (this.isOpenToSee) {
        this.browserOpened();
      }
    },
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

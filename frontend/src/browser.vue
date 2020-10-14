<template>
  <div id="browser">
    <header id="browserHeader">
      <BrowserFilterToolbar />
      <BrowserTitleToolbar />
    </header>
    <BrowserMain />
    <BrowserPaginationToolbar />
  </div>
</template>

<script>
import { mapGetters, mapState } from "vuex";

import BrowserFilterToolbar from "@/components/browser-filter-toolbar";
import BrowserMain from "@/components/browser-main";
import BrowserPaginationToolbar from "@/components/browser-pagination-toolbar";
import BrowserTitleToolbar from "@/components/browser-title-toolbar";

export default {
  name: "Browser",
  components: {
    BrowserFilterToolbar,
    BrowserMain,
    BrowserPaginationToolbar,
    BrowserTitleToolbar,
  },
  computed: {
    ...mapState("auth", {
      user: (state) => state.user,
    }),
    ...mapGetters("auth", ["isOpenToSee"]),
  },
  watch: {
    $route: function (to) {
      this.$store.dispatch("browser/routeChanged", to.params);
    },
    user: function () {
      this.opened();
    },
    isOpenToSee: function () {
      this.opened();
    },
  },
  methods: {
    opened: function () {
      if (this.isOpenToSee) {
        this.$store.dispatch("browser/browserOpened", this.$route.params);
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

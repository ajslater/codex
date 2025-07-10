<template>
  <v-main v-if="isAuthorized" id="browser">
    <BrowserHeader />
    <BrowserMain />
    <BrowserNavToolbar />
    <BrowserSettingsDrawer />
  </v-main>
  <Unauthorized v-else />
</template>

<script>
import { mapActions, mapState } from "pinia";

import BrowserHeader from "@/components/browser/browser-header.vue";
import BrowserSettingsDrawer from "@/components/browser/drawer/browser-settings-drawer.vue";
import BrowserMain from "@/components/browser/main.vue";
import BrowserNavToolbar from "@/components/browser/toolbars/nav/browser-toolbar-nav.vue";
import Unauthorized from "@/components/unauthorized.vue";
import { useAuthStore } from "@/stores/auth";
import { useBrowserStore } from "@/stores/browser";

export default {
  name: "MainBrowser",
  components: {
    BrowserHeader,
    BrowserMain,
    BrowserNavToolbar,
    BrowserSettingsDrawer,
    Unauthorized,
  },
  computed: {
    ...mapState(useAuthStore, {
      user: (state) => state.user,
    }),
    ...mapState(useAuthStore, ["isAuthorized"]),
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
  },
  created() {
    const wait = this.user ? 0 : 300;
    const createdUser = this.user;
    setTimeout(() => {
      if (this.user?.id === createdUser?.id) {
        // Only loadSettings if app.vue didn't login and change the user.
        this.loadSettings();
      }
    }, wait);
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

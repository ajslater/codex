<template>
  <v-main v-if="isAuthorized" id="browser">
    <BrowserHeader />
    <BrowserMain />
    <BrowserNavToolbar />
    <BrowserSettingsDrawer />
    <FilterWarningSnackbar />
  </v-main>
  <Unauthorized v-else />
</template>

<script>
import { mapActions, mapState } from "pinia";

import BrowserHeader from "@/components/browser/browser-header.vue";
import BrowserSettingsDrawer from "@/components/browser/drawer/browser-settings-drawer.vue";
import FilterWarningSnackbar from "@/components/browser/filter-warning-snackbar.vue";
import BrowserMain from "@/components/browser/main.vue";
import BrowserNavToolbar from "@/components/browser/toolbars/nav/browser-toolbar-nav.vue";
import Unauthorized from "@/components/unauthorized.vue";
import { useAuthStore } from "@/stores/auth";
import { useBrowserStore } from "@/stores/browser";
import { useSelectManyStore } from "@/stores/select-many";

export default {
  name: "MainBrowser",
  components: {
    BrowserHeader,
    BrowserMain,
    BrowserNavToolbar,
    BrowserSettingsDrawer,
    FilterWarningSnackbar,
    Unauthorized,
  },
  computed: {
    ...mapState(useAuthStore, {
      user: (state) => state.user,
    }),
    ...mapState(useAuthStore, ["isAuthorized"]),
  },
  watch: {
    $route() {
      window.scrollTo(0, 0);
      this.loadBrowserPage();
      this.deactivateSelectMany();
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
    ...mapActions(useBrowserStore, ["loadBrowserPage", "loadSettings"]),
    ...mapActions(useSelectManyStore, { deactivateSelectMany: "deactivate" }),
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

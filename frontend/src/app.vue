<template>
  <v-app>
    <router-view />
  </v-app>
</template>

<script>
import { mapActions, mapState } from "pinia";

import { useAuthStore } from "@/stores/auth";
import { useCommonStore } from "@/stores/common";
import { useSocketStore } from "@/stores/socket";

export default {
  name: "App",
  computed: {
    ...mapState(useAuthStore, {
      user: (state) => state.user,
    }),
  },
  watch: {
    user(to) {
      if (to) {
        this.setTimezone();
        // If the user changes resubscribe to channels.
        useSocketStore().reopen();
      }
    },
  },
  async created() {
    this.loadAdminFlags();
    /*
     * Boot phase: kick off the independent network requests in
     * parallel. Pre-warming ``loadOPDSURLs`` here means the OPDS
     * dialog opens against cached state instead of waiting on a
     * round-trip when the user clicks the button. ``allSettled``
     * (rather than ``all``) so a failure in one — e.g. the
     * /opds-urls endpoint returning 401 before auth lands —
     * doesn't suppress the others.
     */
    Promise.allSettled([
      this.loadProfile().then(() => this.setTimezone()),
      this.loadOPDSURLs(),
    ]);
  },
  methods: {
    ...mapActions(useAuthStore, [
      "loadAdminFlags",
      "loadProfile",
      "setTimezone",
    ]),
    ...mapActions(useCommonStore, ["loadOPDSURLs"]),
  },
};
</script>

<!-- eslint-disable-next-line vue-scoped-css/enforce-style-type -->
<style lang="scss">
html {
  overflow-y: auto;
}

noscript {
  text-align: center;
  font-family: sans-serif;
  color: rgb(var(--v-theme-textDisabled));
}

a {
  text-decoration: none !important;
  color: rgb(var(--v-theme-primary));
}

.v-overlay__content {
  background-color: rgb(var(--v-theme-background)) !important;
  border-radius: 5px;
}

.v-tooltip > .v-overlay__content {
  color: rgb(var(--v-theme-textDisabled)) !important;
}
</style>

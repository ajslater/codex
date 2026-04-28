<template>
  <v-app>
    <router-view />
    <SessionErrorSnackbar />
  </v-app>
</template>

<script>
import { mapActions, mapState } from "pinia";

import SessionErrorSnackbar from "@/components/session-error-snackbar.vue";
import { useAuthStore } from "@/stores/auth";
import { useSocketStore } from "@/stores/socket";

export default {
  name: "App",
  components: {
    SessionErrorSnackbar,
  },
  computed: {
    ...mapState(useAuthStore, {
      user: (state) => state.user,
      /*
       * Kiosk mode: no per-user account but the server still
       * wants the visitor's timezone for display. Watching this
       * flag alongside ``user`` lets us cover both auth paths
       * without double-firing setTimezone on first authenticated
       * load.
       */
      nonUsers: (state) => state.adminFlags?.nonUsers,
    }),
  },
  watch: {
    user: {
      immediate: true,
      handler(to) {
        if (to) {
          this.setTimezone();
          /* If the user changes resubscribe to channels. */
          useSocketStore().reopen();
        }
      },
    },
    nonUsers: {
      immediate: true,
      handler(to) {
        /*
         * Kiosk path only — when there's a real user the
         * ``user`` watcher above already covers setTimezone.
         */
        if (to && !this.user) {
          this.setTimezone();
        }
      },
    },
  },
  created() {
    /*
     * Boot phase: kick off the independent cold-start network
     * requests at once. ``allSettled`` (rather than ``all``) so
     * a failure in one — e.g. /admin-flags returning 401 before
     * auth lands — doesn't suppress the other. Each store action
     * already swallows its own errors via ``.catch`` so a failed
     * promise here is purely informational.
     *
     * ``setTimezone`` was previously chained off
     * ``loadProfile``, but the ``user`` / ``nonUsers`` watchers
     * cover both auth paths and avoid the double-fire that the
     * chain caused on every authenticated boot.
     */
    Promise.allSettled([this.loadAdminFlags(), this.loadProfile()]);
  },
  methods: {
    ...mapActions(useAuthStore, [
      "loadAdminFlags",
      "loadProfile",
      "setTimezone",
    ]),
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

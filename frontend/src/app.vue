<template>
  <v-app>
    <router-view />
    <SessionErrorSnackbar />
    <DockerHubDeprecatedSnackbar />
  </v-app>
</template>

<script>
import { mapActions, mapState } from "pinia";

import DockerHubDeprecatedSnackbar from "@/components/docker-hub-deprecated-snackbar.vue";
import SessionErrorSnackbar from "@/components/session-error-snackbar.vue";
import { useAuthStore } from "@/stores/auth";
import { useFavoritesStore } from "@/stores/favorites";
import { useSocketStore } from "@/stores/socket";

export default {
  name: "App",
  components: {
    DockerHubDeprecatedSnackbar,
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
          /*
           * Warm the favorites store so star toggles render the
           * user's persisted state on first paint instead of
           * flashing empty. ``hydrate`` is idempotent.
           */
          useFavoritesStore().hydrate();
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
     * Boot phase: single ``/api/v4/session`` composite returns user +
     * adminFlags + permissions + version in one round trip.
     */
    this.loadSession();
  },
  methods: {
    ...mapActions(useAuthStore, ["loadSession", "setTimezone"]),
  },
};
</script>

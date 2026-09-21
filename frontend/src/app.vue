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

<!-- eslint-disable-next-line vue-scoped-css/enforce-style-type -->
<style lang="scss">
html {
  overflow-y: auto;
}

noscript {
  text-align: center;
  font-family: sans-serif;
  color: rgb(var(--v-theme-text-disabled));
}

a {
  text-decoration: none !important;
  color: rgb(var(--v-theme-primary));
}

/*
 * Overlay content boxes are app chrome: menus, dialogs and tooltips sit
 * on the page background instead of Vuetify's own surface colors.
 *
 * Snackbars are the exception. A snackbar's ``color`` prop paints this
 * very element, via Vuetify's ``bg-*`` utility class. That class lives
 * in a cascade layer and this rule does not, so an unlayered
 * ``background-color`` wins here no matter how the snackbar asks.
 * Exempting the wrapper is what makes ``color`` work on a snackbar at
 * all. The radius still applies to every overlay.
 */
.v-overlay__content {
  border-radius: 5px;
}

.v-overlay__content:not(.v-snackbar__wrapper) {
  background-color: rgb(var(--v-theme-background)) !important;
}

.v-tooltip > .v-overlay__content {
  color: rgb(var(--v-theme-text-disabled)) !important;
}
</style>

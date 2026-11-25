<template>
  <v-app>
    <router-view />
    <SessionErrorSnackbar />
    <NoticeSnackbar />
    <DockerHubDeprecatedSnackbar />
  </v-app>
</template>

<script>
import { mapActions, mapState } from "pinia";

import DockerHubDeprecatedSnackbar from "@/components/docker-hub-deprecated-snackbar.vue";
import NoticeSnackbar from "@/components/notice-snackbar.vue";
import SessionErrorSnackbar from "@/components/session-error-snackbar.vue";
import { useAuthStore } from "@/stores/auth";
import { pendingTitle, useOnlineTagStore } from "@/stores/online-tag";
import { useReadingListsStore } from "@/stores/reading-lists";
import { useSocketStore } from "@/stores/socket";

export default {
  name: "App",
  components: {
    DockerHubDeprecatedSnackbar,
    NoticeSnackbar,
    SessionErrorSnackbar,
  },
  head() {
    /*
     * "(N) " on whatever title the page sets, so a background tab shows
     * matches waiting for review. Read the count here, not inside the
     * template function: unhead calls that at render time, outside this
     * effect, so only what head() itself reads re-runs it.
     */
    const count = this.isUserAdmin ? this.pendingComicCount : 0;
    if (!count) return {};
    return { titleTemplate: (title) => pendingTitle(count, title) };
  },
  computed: {
    ...mapState(useOnlineTagStore, ["pendingComicCount"]),
    ...mapState(useAuthStore, ["isUserAdmin"]),
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
           * Warm the user's lists so list buttons render their
           * persisted state on first paint instead of flashing
           * empty. ``hydrate`` clears another user's first.
           */
          useReadingListsStore().hydrate(to.id);
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

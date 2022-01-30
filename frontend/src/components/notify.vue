<template>
  <v-snackbar
    id="notifySnackBar"
    :value="show"
    bottom
    right
    rounded
    width="183"
    :timeout="-1"
  >
    <span v-if="notify === NOTIFY_STATES.LIBRARY_UPDATING">
      Updating Libraries
      <v-progress-circular size="18" indeterminate color="#cc7b19" />
    </span>
    <span v-else-if="notify === NOTIFY_STATES.FAILED">
      Review failed imports in the
      <a :href="FAILED_IMPORT_URL" target="_blank">Admin Panel</a>
    </span>
    <v-btn
      id="dismissNotifySnackBar"
      title="dismiss notification"
      x-small
      ripple
      @click="dismiss"
      >x</v-btn
    >
  </v-snackbar>
</template>

<script>
import { mapGetters, mapState } from "vuex";

import { FAILED_IMPORT_URL } from "@/api/v2/notify";
import { NOTIFY_STATES } from "@/store/modules/notify";

const SHOW_STATES = new Set([
  NOTIFY_STATES.LIBRARY_UPDATING,
  NOTIFY_STATES.FAILED,
]);

export default {
  name: "NotifySnackBar",
  data() {
    return {
      FAILED_IMPORT_URL,
      NOTIFY_STATES,
    };
  },
  computed: {
    ...mapState("notify", {
      notify: (state) => state.notify,
    }),
    ...mapGetters("auth", ["isAdmin"]),
    show: function () {
      return SHOW_STATES.has(this.notify);
    },
  },
  watch: {
    isAdmin: function (to) {
      if (to) {
        // If we switch to an admin user, check notifications.
        this.$store.dispatch("notify/notifyChanged", NOTIFY_STATES.CHECK);
      }
    },
  },
  methods: {
    dismiss: function () {
      const state =
        this.notify === NOTIFY_STATES.FAILED
          ? NOTIFY_STATES.OFF
          : NOTIFY_STATES.DISMISSED;
      this.$store.dispatch("notify/notifyChanged", state);
    },
  },
};
</script>

<style scoped lang="scss">
#dismissNotifySnackBar {
  margin-left: 5px;
}
</style>

<!-- eslint-disable-next-line vue-scoped-css/enforce-style-type -->
<style lang="scss">
/* I have no idea why this is necessary but it really is */
#notifySnackBar > .v-sheet.v-snack__wrapper {
  min-width: 222px;
}
</style>

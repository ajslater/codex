<template>
  <v-snackbar
    id="notifyScanning"
    :value="show"
    bottom
    right
    rounded
    width="183"
    :timeout="-1"
  >
    <span v-if="notify === NOTIFY_STATES.SCANNING">
      Scanning Libraries
      <v-progress-circular size="18" indeterminate color="#cc7b19" />
    </span>
    <span v-else-if="notify === NOTIFY_STATES.FAILED">
      Review failed imports in the
      <a :href="FAILED_IMPORT_URL">Admin Panel</a>
    </span>
    <v-btn
      id="dismissNotifyScanning"
      title="dismiss notification"
      x-small
      ripple
      @click="dismiss()"
      >x</v-btn
    >
  </v-snackbar>
</template>

<script>
import { mapGetters, mapState } from "vuex";

import { FAILED_IMPORT_URL } from "@/api/v1/notify";
import { NOTIFY_STATES } from "@/store/modules/notify";

const SHOW_STATES = new Set([NOTIFY_STATES.SCANNING, NOTIFY_STATES.FAILED]);

export default {
  name: "NotifyScan",
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
        this.$store.dispatch("notify/setNotify", NOTIFY_STATES.CHECK);
      }
    },
  },
  methods: {
    dismiss: function () {
      this.$store.dispatch("notify/setNotify", NOTIFY_STATES.DISMISSED);
    },
  },
};
</script>

<style scoped lang="scss">
#dismissNotifyScanning {
  margin-left: 5px;
}
</style>

<!-- eslint-disable vue-scoped-css/require-scoped -->
<style lang="scss">
/* I have no idea why this is neccessary but it really is */
#notifyScanning > .v-snack__wrapper {
  min-width: 183px;
}
</style>
<!-- eslint-enable vue-scoped-css/require-scoped -->

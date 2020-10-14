<template>
  <v-app>
    <router-view />
    <NotifyScan />
  </v-app>
</template>

<script>
import { mapState } from "vuex";

import NotifyScan from "@/components/notify-scan";

export default {
  name: "App",
  components: {
    NotifyScan,
  },
  computed: {
    ...mapState("auth", {
      user: (state) => state.user,
    }),
    ...mapState({
      isConnected: (state) => state.socket.isConnected,
    }),
  },
  watch: {
    user: function () {
      this.wsSubscribe();
    },
    isConnected(to) {
      if (to) {
        this.wsSubscribe();
      }
    },
  },
  beforeCreate() {
    // First thing we do is see if we're logged in
    return this.$store.dispatch("auth/me").then(() => {
      console.debug("socket connecting...");
      return this.$connect();
    });
  },
  methods: {
    wsSubscribe() {
      this.$store.dispatch("notify/subscribe");
    },
  },
};
</script>

<!-- eslint-disable-next-line vue-scoped-css/require-scoped -->
<style lang="scss">
body {
  background-color: #121212;
}
</style>

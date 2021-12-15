<template>
  <v-app>
    <router-view />
    <NotifySnackBar />
  </v-app>
</template>

<script>
import { mapState } from "vuex";

import NotifySnackBar from "@/components/notify";

export default {
  name: "App",
  components: {
    NotifySnackBar,
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
  async beforeCreate() {
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

<!-- eslint-disable-next-line vue-scoped-css/enforce-style-type -->
<style lang="scss">
body {
  background-color: #121212;
}
</style>

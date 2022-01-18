<template>
  <v-app>
    <router-view />
    <SettingsDrawer />
    <NotifySnackBar />
  </v-app>
</template>

<script>
import { mapState } from "vuex";

import NotifySnackBar from "@/components/notify";
import SettingsDrawer from "@/components/settings-drawer";

export default {
  name: "App",
  components: {
    SettingsDrawer,
    NotifySnackBar,
  },
  computed: {
    ...mapState({
      isConnected: (state) => state.socket.isConnected,
    }),
    ...mapState("auth", {
      user: (state) => state.user,
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

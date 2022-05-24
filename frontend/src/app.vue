<template>
  <v-app>
    <router-view />
    <SettingsDrawer />
    <NotifySnackBar />
  </v-app>
</template>

<script>
import { mapActions, mapState } from "vuex";

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
      this.subscribe();
    },
    isConnected(to) {
      if (to) {
        this.subscribe();
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
    ...mapActions("notify", ["subscribe"]),
  },
};
</script>

<!-- eslint-disable-next-line vue-scoped-css/enforce-style-type -->
<style lang="scss">
html {
  overflow-y: auto;
}
body {
  background-color: #121212;
}
</style>

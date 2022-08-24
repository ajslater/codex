<template>
  <v-app>
    <router-view />
  </v-app>
</template>

<script>
import { mapActions, mapState } from "vuex";

export default {
  name: "App",
  computed: {
    ...mapState("socket", {
      isConnected: (state) => state.isConnected,
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
  async created() {
    this.setTimezone();
    this.getAdminFlags();
    this.getProfile();
    return this.$connect();
  },
  methods: {
    ...mapActions("auth", ["getProfile", "setTimezone", "getAdminFlags"]),
    ...mapActions("socket", ["subscribe"]),
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
noscript {
  text-align: center;
  font-family: sans-serif;
  color: darkgray;
}
a {
  text-decoration: none !important;
}
a:hover,
a:hover .v-icon {
  color: white !important;
}
a .v-icon {
  color: #cc7b19 !important;
}
a.v-btn .v-icon {
  color: white !important;
}
</style>

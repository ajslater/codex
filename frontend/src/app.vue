<template>
  <v-app>
    <router-view />
  </v-app>
</template>

<script>
import { mapActions, mapState } from "pinia";

import { useAuthStore } from "@/stores/auth";
import { useSocketStore } from "@/stores/socket";

export default {
  name: "App",
  computed: {
    ...mapState(useSocketStore, {
      isConnected: (state) => state.isConnected,
    }),
    ...mapState(useAuthStore, {
      user: (state) => state.user,
    }),
  },
  watch: {
    user: function () {
      this.setTimezone();
      this.sendSubscribe();
    },
    isConnected(to) {
      if (to) {
        this.sendSubscribe();
      }
    },
  },
  async created() {
    this.setTimezone();
    this.loadAdminFlags();
    this.loadProfile();
  },
  methods: {
    ...mapActions(useAuthStore, [
      "loadAdminFlags",
      "loadProfile",
      "setTimezone",
    ]),
    ...mapActions(useSocketStore, ["sendSubscribe"]),
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
.v-dialog,
.v-navigation-drawer {
  background-color: #202020 !important;
}

.background-highlight,
.highlight-table tr:nth-child(even),
.highlight-table th {
  background-color: #121212 !important;
}
.background-soft-highlight {
  background-color: #272727 !important;
}
</style>

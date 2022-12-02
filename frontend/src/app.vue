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
noscript {
  text-align: center;
  font-family: sans-serif;
  color: rgb(var(--v-theme-textDisabled));
}
.test {
  color: rgb(var(--v-theme-textSecondary));
}
a {
  text-decoration: none !important;
}
.v-dialog,
.v-navigation-drawer {
  background-color: rgb(var(--v-theme-background)) !important;
}

.background-highlight,
.highlight-table tr:nth-child(even),
.highlight-table th {
  background-color: rgb(var(--v-theme-surface)) !important;
}
.background-soft-highlight {
  background-color: rgb(var(--v-theme-surface)) !important;
}
.codexToolbar {
  position: fixed !important;
  z-index: 20 !important;
}

.settingsDrawer {
  z-index: 30 !important;
}

.settingsDrawerContainer {
  position: relative !important;
  display: flex;
  flex-direction: column;
  justify-content: space-between;
  height: 100%;
}

.settingsDrawer .v-icon {
  color: rgb(var(--v-theme-iconsInactive)) !important;
  margin-right: 0.33em;
}
</style>

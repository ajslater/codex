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
    // First thing we do is see if we're logged in
    return this.me().then(() => {
      return this.$connect();
    });
  },
  methods: {
    ...mapActions("auth", ["me"]),
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
</style>

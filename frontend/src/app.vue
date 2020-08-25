<template>
  <v-app>
    <router-view />
  </v-app>
</template>

<script>
export default {
  name: "App",
  beforeCreate() {
    // First thing we do is see if we're logged in
    this.$store.dispatch("auth/me");
  },
};
</script>

<!-- eslint-disable vue-scoped-css/require-scoped -->
<style lang="scss">
body {
  background-color: #121212;
}
</style>
<!-- eslint-enable vue-scoped-css/require-scoped -->

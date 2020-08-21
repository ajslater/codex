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

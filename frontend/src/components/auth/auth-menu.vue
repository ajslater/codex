<template>
  <div>
    <v-divider />
    <div v-if="user">
      <v-list-item ripple @click="logout">
        <v-list-item-content>
          <v-list-item-title> Logout {{ user.username }} </v-list-item-title>
        </v-list-item-content>
      </v-list-item>
      <AuthChangePasswordDialog />
    </div>
    <AuthLoginDialog v-else />
  </div>
</template>

<script>
import { mapActions, mapState } from "pinia";

import AuthChangePasswordDialog from "@/components/auth/auth-change-password-dialog.vue";
import AuthLoginDialog from "@/components/auth/login-dialog.vue";
import { useAuthStore } from "@/stores/auth";

export default {
  name: "AuthMenu",
  components: {
    AuthChangePasswordDialog,
    AuthLoginDialog,
  },
  data: function () {
    return {
      item: undefined,
    };
  },
  computed: {
    ...mapState(useAuthStore, {
      user: (state) => state.user,
    }),
  },
  methods: {
    ...mapActions(useAuthStore, ["logout"]),
  },
};
</script>

<style scoped lang="scss"></style>

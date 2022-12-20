<template>
  <AuthLogoutItem v-if="user" />
  <ChangePasswordDialog v-if="user" :user="user" />
  <AuthLoginDialog v-else />
</template>

<script>
import { mapActions, mapState } from "pinia";

import AuthLoginDialog from "@/components/auth/login-dialog.vue";
import AuthLogoutItem from "@/components/auth/logout-item.vue";
import ChangePasswordDialog from "@/components/change-password-dialog.vue";
import { useAuthStore } from "@/stores/auth";

export default {
  name: "AuthMenu",
  components: {
    ChangePasswordDialog,
    AuthLoginDialog,
    AuthLogoutItem,
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

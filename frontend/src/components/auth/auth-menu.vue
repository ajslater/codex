<template>
  <div>
    <div v-if="user">
      <AuthLogoutItem />
      <ChangePasswordDialog :user="user" />
    </div>
    <AuthLoginDialog v-else />
  </div>
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

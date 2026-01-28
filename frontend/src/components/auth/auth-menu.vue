<template>
  <div v-if="user">
    <CodexListItem
      :prepend-icon="mdiLogout"
      :title="logoutTitle"
      @click.stop="logout"
    />
    <ChangePasswordDialog v-if="showChangePassword" :user="user" />
    <AuthTokenDialog :user="user" />
  </div>
  <AuthLoginDialog v-else />
</template>

<script>
import { mdiLogout } from "@mdi/js";
import { mapActions, mapState } from "pinia";

import AuthTokenDialog from "@/components/auth/auth-token.vue";
import ChangePasswordDialog from "@/components/auth/change-password-dialog.vue";
import AuthLoginDialog from "@/components/auth/login-dialog.vue";
import CodexListItem from "@/components/codex-list-item.vue";
import { useAuthStore } from "@/stores/auth";

export default {
  name: "AuthMenu",
  components: {
    AuthLoginDialog,
    AuthTokenDialog,
    ChangePasswordDialog,
    CodexListItem,
  },
  props: {
    showChangePassword: {
      type: Boolean,
      default: true,
    },
  },
  data() {
    return {
      mdiLogout,
    };
  },
  computed: {
    ...mapState(useAuthStore, {
      user: (state) => state.user,
    }),
    logoutTitle() {
      return `Logout ${this.user.username}`;
    },
  },
  methods: {
    ...mapActions(useAuthStore, ["logout"]),
  },
};
</script>

<template>
  <div v-if="user">
    <CodexListItem
      :prepend-icon="mdiLogout"
      :title="logoutTitle"
      @click.stop="logout"
    />
    <ProfileDialog v-if="showExtras" />
    <AuthTokenDialog v-if="showExtras" :user="user" />
  </div>
  <AuthLoginDialog v-else />
</template>

<script>
import { mdiLogout } from "@mdi/js";
import { mapActions, mapState } from "pinia";

import AuthTokenDialog from "@/components/auth/auth-token.vue";
import AuthLoginDialog from "@/components/auth/login-dialog.vue";
import ProfileDialog from "@/components/auth/profile-dialog.vue";
import CodexListItem from "@/components/codex-list-item.vue";
import { useAuthStore } from "@/stores/auth";

export default {
  name: "AuthMenu",
  components: {
    AuthLoginDialog,
    AuthTokenDialog,
    ProfileDialog,
    CodexListItem,
  },
  props: {
    showExtras: {
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

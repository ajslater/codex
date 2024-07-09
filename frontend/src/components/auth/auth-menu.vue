<template>
  <DrawerItem
    v-if="user"
    :prepend-icon="mdiLogout"
    :title="logoutTitle"
    @click.stop="logout"
  />
  <ChangePasswordDialog v-if="user" :user="user" />
  <AuthLoginDialog v-else />
</template>

<script>
import { mdiLogout } from "@mdi/js";
import { mapActions, mapState } from "pinia";

import ChangePasswordDialog from "@/components/auth/change-password-dialog.vue";
import AuthLoginDialog from "@/components/auth/login-dialog.vue";
import DrawerItem from "@/components/drawer-item.vue";
import { useAuthStore } from "@/stores/auth";

export default {
  name: "AuthMenu",
  components: {
    AuthLoginDialog,
    ChangePasswordDialog,
    DrawerItem,
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

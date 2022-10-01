<template>
  <div>
    <v-divider />
    <div v-if="user">
      <v-list-item ripple @click="logout">
        <v-list-item-content>
          <v-list-item-title>
            <v-icon>{{ mdiLogout }}</v-icon
            >Logout {{ user.username }}
          </v-list-item-title>
        </v-list-item-content>
      </v-list-item>
      <ChangePasswordDialog :user="user" />
    </div>
    <AuthLoginDialog v-else />
  </div>
</template>

<script>
import { mdiLogout } from "@mdi/js";
import { mapActions, mapState } from "pinia";

import AuthLoginDialog from "@/components/auth/login-dialog.vue";
import ChangePasswordDialog from "@/components/change-password-dialog.vue";
import { useAuthStore } from "@/stores/auth";

export default {
  name: "AuthMenu",
  components: {
    ChangePasswordDialog,
    AuthLoginDialog,
  },
  data: function () {
    return {
      mdiLogout,
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

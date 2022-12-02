<template>
  <v-list-item @click="logout">
    <v-list-item-title>
      <v-icon>{{ mdiLogout }}</v-icon
      >Logout {{ username }}
    </v-list-item-title>
  </v-list-item>
</template>

<script>
import { mdiLogout } from "@mdi/js";
import { mapActions, mapState } from "pinia";

import { useAuthStore } from "@/stores/auth";

export default {
  name: "AuthLogoutItem",
  data: function () {
    return {
      mdiLogout,
    };
  },
  computed: {
    ...mapState(useAuthStore, {
      username: (state) => state.user.username,
    }),
  },
  methods: {
    ...mapActions(useAuthStore, ["logout"]),
  },
};
</script>

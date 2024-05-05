<template>
  <v-main>
    <v-empty-state
      class="empty"
      headline="Unauthorized"
      :text="text"
      :icon="mdiLockOutline"
    >
      <div class="login">
        <AuthMenu />
      </div>
    </v-empty-state>
  </v-main>
</template>

<script>
import { mdiLockOutline } from "@mdi/js";
import { mapGetters, mapState } from "pinia";

import AuthMenu from "@/components/auth/auth-menu.vue";
import { useAuthStore } from "@/stores/auth";

export default {
  name: "UnauthorizedEmptyState",
  components: {
    AuthMenu,
  },
  props: {
    admin: {
      type: Boolean,
      default: false,
    },
  },
  data() {
    return {
      mdiLockOutline,
    };
  },
  computed: {
    ...mapGetters(useAuthStore, ["isCodexViewable", "isUserAdmin"]),
    ...mapState(useAuthStore, {
      registration: (state) => state.adminFlags.registration,
    }),
    text() {
      return this.registration ? "" : "Registration is disabled";
    },
  },
};
</script>

<style scoped lang="scss">
.empty {
  color: rgb(var(--v-theme-textDisabled));
}
.login {
  color: rgb(var(--v-theme-primary));
}
</style>

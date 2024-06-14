<template>
  <v-main id="unauthorized">
    <v-empty-state
      v-if="isAuthChecked"
      class="empty"
      headline="Unauthorized"
      :text="text"
      :icon="mdiLockOutline"
    >
      <div class="login">
        <AuthMenu />
      </div>
    </v-empty-state>
    <PlaceholderLoading v-else id="unauthorizedPlaceholder" />
  </v-main>
</template>

<script>
import { mdiLockOutline } from "@mdi/js";
import { mapGetters, mapState } from "pinia";

import AuthMenu from "@/components/auth/auth-menu.vue";
import PlaceholderLoading from "@/components/placeholder-loading.vue";
import { useAuthStore } from "@/stores/auth";

export default {
  name: "UnauthorizedEmptyState",
  components: {
    AuthMenu,
    PlaceholderLoading,
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
    ...mapGetters(useAuthStore, [
      "isAuthChecked",
      "isAuthorized",
      "isUserAdmin",
    ]),
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
#unauthorized {
  padding-top: max(20px, env(safe-area-inset-top));
  padding-left: max(20px, env(safe-area-inset-left));
  padding-right: max(20px, env(safe-area-inset-right));
  padding-bottom: max(20px,env(safe-area-inset-bottom));
}
#unauthorizedPlaceholder {
  position: fixed;
  top: 25%;
  left: 25%;
}
.empty {
  color: rgb(var(--v-theme-textDisabled));
}
.login {
  color: rgb(var(--v-theme-primary));
}
</style>

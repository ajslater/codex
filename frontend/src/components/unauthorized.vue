<template>
  <v-main id="unauthorized">
    <AppBanner />
    <EmptyState
      v-if="isAuthChecked"
      class="empty"
      headline="Unauthorized"
      :text="text"
      :icon="mdiLockOutline"
    >
      <div class="login">
        <AdminBrowserLink v-if="showAdminBrowserLink" />
        <AuthMenu :show-change-password="false" />
      </div>
    </EmptyState>
    <PlaceholderLoading v-else id="unauthorizedPlaceholder" />
  </v-main>
</template>

<script>
import { mdiLockOutline } from "@mdi/js";
import { mapState } from "pinia";

import AdminBrowserLink from "@/components/admin/browser-link.vue";
import AuthMenu from "@/components/auth/auth-menu.vue";
import AppBanner from "@/components/banner.vue";
import EmptyState from "@/components/empty.vue";
import PlaceholderLoading from "@/components/placeholder-loading.vue";
import { useAuthStore } from "@/stores/auth";

export default {
  name: "UnauthorizedEmptyState",
  components: {
    AppBanner,
    AdminBrowserLink,
    AuthMenu,
    PlaceholderLoading,
    EmptyState,
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
    ...mapState(useAuthStore, ["isAuthChecked", "isAuthorized", "isUserAdmin"]),
    ...mapState(useAuthStore, {
      showAdminBrowserLink(state) {
        return (
          this.$router.currentRoute?.value?.name?.startsWith("admin") &&
          state.adminFlags.nonUsers
        );
      },
      text(state) {
        return state.adminFlags.registration ? "" : "Registration is disabled";
      },
    }),
  },
};
</script>

<style scoped lang="scss">
#unauthorized {
  padding-top: max(20px, env(safe-area-inset-top));
  padding-left: max(20px, env(safe-area-inset-left));
  padding-right: max(20px, env(safe-area-inset-right));
  padding-bottom: max(20px, env(safe-area-inset-bottom));
}

#unauthorizedPlaceholder {
  position: fixed;
  top: 25%;
  left: 25%;
}

.login {
  color: rgb(var(--v-theme-primary));
}

.login :deep(.v-list-item__prepend) {
  margin-right: 0.25em;
}
</style>

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
        <SsoLoginButton class="ssoButton" />
        <AuthMenu :show-extras="false" />
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
import SsoLoginButton from "@/components/auth/sso-login-button.vue";
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
    SsoLoginButton,
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
/* Layered: these rules beat Vuetify's component CSS by position,
 * and lose to a `color`/utility prop, which is the intended order. */
@layer codex-components {
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

  .ssoButton {
    margin-bottom: 0.75em;
  }

  .login :deep(.v-list-item__prepend) {
    margin-right: 0.25em;
  }
}
</style>

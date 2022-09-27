<template>
  <div>
    <AuthMenu />
    <component :is="adminMenuLoader" />
  </div>
</template>

<script>
import { mapGetters } from "pinia";

import { useAuthStore } from "@/stores/auth";

const AdminMenu = () => import("@/components/admin/admin-menu.vue");
import AuthMenu from "@/components/auth/auth-menu.vue";
import SettingsFooter from "@/components/settings/settings-footer.vue";

export default {
  name: "SettingsCommonPanel",
  components: {
    AuthMenu,
    SettingsFooter,
  },
  props: {
    admin: { type: Boolean, default: true },
  },
  data() {
    return {
      // Could calculate this server side, but whatever
    };
  },
  computed: {
    ...mapGetters(useAuthStore, ["isUserAdmin"]),
    adminMenuLoader: function () {
      return this.admin && this.isUserAdmin ? AdminMenu : undefined;
    },
  },
};
</script>

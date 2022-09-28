<template>
  <div>
    <AuthMenu />
    <component :is="adminMenuLoader" :menu="adminMenu" />
  </div>
</template>

<script>
import { mapGetters } from "pinia";

import { useAuthStore } from "@/stores/auth";

const AdminMenu = () => import("@/components/admin/admin-menu.vue");
import AuthMenu from "@/components/auth/auth-menu.vue";

export default {
  name: "SettingsCommonPanel",
  components: {
    AuthMenu,
  },
  props: {
    adminMenu: { type: Boolean, default: true },
  },
  computed: {
    ...mapGetters(useAuthStore, ["isUserAdmin"]),
    adminMenuLoader: function () {
      return this.isUserAdmin ? AdminMenu : undefined;
    },
  },
};
</script>

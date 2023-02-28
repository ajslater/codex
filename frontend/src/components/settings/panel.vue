<template>
  <div id="commonPanel">
    <AuthMenu />
    <v-divider v-if="isUserAdmin" />
    <component :is="AdminMenu" v-if="isUserAdmin" :menu="adminMenu" />
  </div>
</template>

<script>
import { mapGetters } from "pinia";
import { defineAsyncComponent, markRaw } from "vue";

import { useAuthStore } from "@/stores/auth";

const AdminMenu = markRaw(
  defineAsyncComponent(() => import("@/components/admin/drawer/admin-menu.vue"))
);
import AuthMenu from "@/components/auth/auth-menu.vue";

export default {
  name: "SettingsCommonPanel",
  components: {
    AuthMenu,
  },
  props: {
    adminMenu: { type: Boolean, default: true },
  },
  data() {
    return { AdminMenu };
  },
  computed: {
    ...mapGetters(useAuthStore, ["isUserAdmin"]),
  },
};
</script>
<style scoped lang="scss">
#commonPanel {
  background-color: rgb(var(--v-theme-background));
}
</style>

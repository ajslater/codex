<template>
  <v-main v-if="isUserAdmin">
    <AdminHeader />
    <AdminTabs />
    <AdminSettingsDrawer />
  </v-main>
  <Unauthorized v-else />
</template>

<script>
import { mdiLogin } from "@mdi/js";
import { mapState } from "pinia";

import AdminHeader from "@/components/admin/admin-header.vue";
import AdminSettingsDrawer from "@/components/admin/drawer/admin-settings-drawer.vue";
import AdminTabs from "@/components/admin/tabs/tabs.vue";
import Unauthorized from "@/components/unauthorized.vue";
import { useAuthStore } from "@/stores/auth";

export default {
  name: "MainAdmin",
  components: {
    AdminHeader,
    AdminSettingsDrawer,
    AdminTabs,
    Unauthorized,
  },
  data() {
    return {
      mdiLogin,
    };
  },
  computed: {
    ...mapState(useAuthStore, ["isUserAdmin"]),
  },
};
</script>

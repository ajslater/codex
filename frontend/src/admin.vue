<template>
  <v-main v-if="isUserAdmin">
    <AdminTitleToolbar />
    <AdminTabs />
    <AdminSettingsDrawer />
  </v-main>
  <Unauthorized v-else />
</template>

<script>
import { mdiLogin } from "@mdi/js";
import { mapGetters } from "pinia";

import AdminTitleToolbar from "@/components/admin/admin-title-toolbar.vue";
import AdminSettingsDrawer from "@/components/admin/drawer/admin-settings-drawer.vue";
import AdminTabs from "@/components/admin/tabs/tabs.vue";
import Unauthorized from "@/components/unauthorized.vue";
import { useAuthStore } from "@/stores/auth";

export default {
  name: "MainAdmin",
  components: {
    AdminTitleToolbar,
    AdminTabs,
    AdminSettingsDrawer,
    Unauthorized,
  },
  data() {
    return {
      mdiLogin,
    };
  },
  computed: {
    ...mapGetters(useAuthStore, ["isUserAdmin"]),
  },
};
</script>

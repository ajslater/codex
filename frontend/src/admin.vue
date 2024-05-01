<template>
  <v-main v-if="isUserAdmin">
    <AdminTitleToolbar />
    <AdminTabs />
  </v-main>
  <Unauthorized v-else :admin="true" />
  <SettingsDrawer title="Admin" :admin="true" :panel="AdminSettingsPanel" />
</template>

<script>
import { mdiLogin } from "@mdi/js";
import { mapGetters } from "pinia";
import { markRaw } from "vue";

import AdminSettingsPanel from "@/components/admin/admin-settings-panel.vue";
import AdminTitleToolbar from "@/components/admin/admin-title-toolbar.vue";
import AdminTabs from "@/components/admin/tabs.vue";
import SettingsDrawer from "@/components/settings/settings-drawer.vue";
import Unauthorized from "@/components/unauthorized.vue";
import { useAuthStore } from "@/stores/auth";

export default {
  name: "MainAdmin",
  components: {
    AdminTitleToolbar,
    AdminTabs,
    SettingsDrawer,
    Unauthorized,
  },
  data() {
    return {
      AdminSettingsPanel: markRaw(AdminSettingsPanel),
      mdiLogin,
    };
  },
  computed: {
    ...mapGetters(useAuthStore, ["isUserAdmin"]),
  },
};
</script>

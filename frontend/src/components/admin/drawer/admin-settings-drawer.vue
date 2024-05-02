<template>
  <SettingsDrawer title="Admin" :temporary="mobile">
    <template #panel>
      <AdminSettingsPanel />
    </template>
  </SettingsDrawer>
</template>
<script>
import AdminSettingsPanel from "@/components/admin/drawer/admin-settings-panel.vue";
import SettingsDrawer from "@/components/settings/settings-drawer.vue";

export default {
  name: "AdminSettingsDrawer",
  components: {
    SettingsDrawer,
    AdminSettingsPanel,
  },
  computed: {
    mobile() {
      return this.$vuetify.display.mobile;
    },
  },
};
</script>

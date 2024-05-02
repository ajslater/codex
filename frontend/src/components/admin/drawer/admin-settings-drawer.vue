<template>
  <SettingsDrawer title="Admin" :temporary="mobile">
    <template #panel>
      <AdminSettingsPanel />
    </template>
  </SettingsDrawer>
</template>
<script>
import { mapActions } from "pinia";

import AdminSettingsPanel from "@/components/admin/drawer/admin-settings-panel.vue";
import SettingsDrawer from "@/components/settings/settings-drawer.vue";
import { useCommonStore } from "@/stores/common";

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
  mounted() {
    if (!this.mobile) {
      this.setSettingsDrawerOpen(true);
    }
  },
  methods: {
    ...mapActions(useCommonStore, ["setSettingsDrawerOpen"]),
  },
};
</script>

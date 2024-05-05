<template>
  <SettingsDrawer title="Admin" :temporary="lgAndDown">
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
    lgAndDown() {
      return this.$vuetify.display.lgAndDown;
    },
  },
  watch: {
    lgAndDown(to) {
      if (!to) {
        this.setSettingsDrawerOpen(true);
      }
    },
  },
  mounted() {
    if (!this.lgAndDown) {
      this.setSettingsDrawerOpen(true);
    }
  },
  methods: {
    ...mapActions(useCommonStore, ["setSettingsDrawerOpen"]),
  },
};
</script>

<template>
  <SettingsDrawer title="Browser" temporary disable-resize-watcher>
    <template #panel>
      <BrowserSettingsPanel />
    </template>
  </SettingsDrawer>
</template>
<script>
import BrowserSettingsPanel from "@/components/browser/drawer/browser-settings-panel.vue";
import SettingsDrawer from "@/components/settings/settings-drawer.vue";

export default {
  name: "BrowserSettingsDrawer",
  components: {
    SettingsDrawer,
    BrowserSettingsPanel,
  },
};
</script>

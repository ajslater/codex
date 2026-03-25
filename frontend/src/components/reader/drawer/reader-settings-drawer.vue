<template>
  <SettingsDrawer title="Reader" temporary disable-resize-watcher>
    <template #panel>
      <ReaderSettingsPanel />
    </template>
  </SettingsDrawer>
</template>
<script>
import ReaderSettingsPanel from "@/components/reader/drawer/reader-settings-panel.vue";
import SettingsDrawer from "@/components/settings/settings-drawer.vue";

export default {
  name: "ReaderSettingsDrawer",
  components: {
    SettingsDrawer,
    ReaderSettingsPanel,
  },
};
</script>

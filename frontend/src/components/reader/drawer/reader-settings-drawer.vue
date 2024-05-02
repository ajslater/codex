<template>
  <SettingsDrawer title="Reader" temporary disable-resize-watcher>
    <template #panel>
      <ReaderSettingsSuperPanel />
    </template>
  </SettingsDrawer>
</template>
<script>
import ReaderSettingsSuperPanel from "@/components/reader/drawer/reader-settings-super-panel.vue";
import SettingsDrawer from "@/components/settings/settings-drawer.vue";

export default {
  name: "ReaderSettingsDrawer",
  components: {
    SettingsDrawer,
    ReaderSettingsSuperPanel,
  },
};
</script>

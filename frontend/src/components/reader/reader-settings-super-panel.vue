<template>
  <ReaderSettingsPanel />
  <v-divider />
  <ReaderKeyboardShortcutsPanel />
  <v-divider />
  <DownloadPanel />
</template>
<script>
import DownloadPanel from "@/components/reader/download-panel.vue";
import ReaderKeyboardShortcutsPanel from "@/components/reader/keyboard-shortcuts-panel.vue";
import ReaderSettingsPanel from "@/components/reader/reader-settings-panel.vue";

export default {
  name: "ReaderSettingsSuperPanel",
  components: {
    DownloadPanel,
    ReaderKeyboardShortcutsPanel,
    ReaderSettingsPanel,
  },
};
</script>

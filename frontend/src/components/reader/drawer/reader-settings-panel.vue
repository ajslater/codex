<template>
  <ReaderSettingsScope />
  <ReaderSettingsReader />
  <v-divider />
  <ReaderKeyboardShortcutsPanel />
  <v-divider />
  <DownloadPanel />
</template>
<script>
import DownloadPanel from "@/components/reader/drawer/download-panel.vue";
import ReaderKeyboardShortcutsPanel from "@/components/reader/drawer/keyboard-shortcuts-panel.vue";
import ReaderSettingsReader from "./reader-settings-reader.vue";
import ReaderSettingsScope from "./reader-settings-scope.vue";

export default {
  name: "ReaderSettingsPanel",
  components: {
    DownloadPanel,
    ReaderKeyboardShortcutsPanel,
    ReaderSettingsReader,
    ReaderSettingsScope,
  },
};
</script>

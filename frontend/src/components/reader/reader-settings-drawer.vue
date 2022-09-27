<template>
  <v-navigation-drawer
    id="readerSettingsDrawer"
    v-model="isSettingsDrawerOpen"
    app
    right
    temporary
    touchless
  >
    <div v-if="isCodexViewable" id="settingsDrawerContainer">
      <div id="topBlock">
        <ReaderSettingsPanel />
        <v-divider />
        <ReaderKeyboardShortcutsPanel />
        <v-divider />
        <DownloadPanel />
        <v-divider />
        <SettingsCommonPanel />
      </div>
      <SettingsFooter />
    </div>
    <template #append>
      <VersionFooter />
    </template>
  </v-navigation-drawer>
</template>

<script>
import { mapGetters, mapWritableState } from "pinia";

import DownloadPanel from "@/components/reader/download-panel.vue";
import ReaderKeyboardShortcutsPanel from "@/components/reader/keyboard-shortcuts-panel.vue";
import ReaderSettingsPanel from "@/components/reader/reader-settings-panel.vue";
import SettingsCommonPanel from "@/components/settings/panel.vue";
import SettingsFooter from "@/components/settings/settings-footer.vue";
import VersionFooter from "@/components/settings/version-footer.vue";
import { useAuthStore } from "@/stores/auth";
import { useReaderStore } from "@/stores/reader";

export default {
  name: "ReaderSettingsPanel",
  components: {
    ReaderKeyboardShortcutsPanel,
    ReaderSettingsPanel,
    SettingsCommonPanel,
    DownloadPanel,
    SettingsFooter,
    VersionFooter,
  },
  computed: {
    ...mapGetters(useAuthStore, ["isCodexViewable"]),
    ...mapWritableState(useReaderStore, ["isSettingsDrawerOpen"]),
  },
};
</script>

<style scoped lang="scss">
#readerSettingsDrawer {
  z-index: 20;
}
@import "../settings/settings-drawer.scss";
</style>

<template>
  <v-navigation-drawer
    id="browserSettingsDrawer"
    v-model="isSettingsDrawerOpen"
    class="settingsDrawer"
    app
    right
    temporary
    touchless
  >
    <div class="settingsDrawerContainer">
      <div id="topBlock">
        <div v-if="isCodexViewable">
          <BrowserSettingsPanel />
          <v-divider />
          <SearchHelp />
          <v-divider />
        </div>
        <SettingsCommonPanel />
        <v-divider />
      </div>
      <SettingsFooter />
    </div>
    <template #append>
      <VersionFooter />
    </template>
  </v-navigation-drawer>
</template>

<script>
import { mapActions, mapGetters, mapWritableState } from "pinia";

import BrowserSettingsPanel from "@/components/browser/browser-settings-panel.vue";
import SearchHelp from "@/components/browser/search-help.vue";
import SettingsCommonPanel from "@/components/settings/panel.vue";
import SettingsFooter from "@/components/settings/settings-footer.vue";
import VersionFooter from "@/components/settings/version-footer.vue";
import { useAuthStore } from "@/stores/auth";
import { useBrowserStore } from "@/stores/browser";

export default {
  name: "BrowserSettingsDialog",
  components: {
    BrowserSettingsPanel,
    SearchHelp,
    SettingsCommonPanel,
    SettingsFooter,
    VersionFooter,
  },
  computed: {
    ...mapGetters(useAuthStore, ["isCodexViewable"]),
    ...mapWritableState(useBrowserStore, ["isSettingsDrawerOpen"]),
  },
  methods: {
    ...mapActions(useBrowserStore, ["setIsSettingsDrawerOpen"]),
  },
};
</script>

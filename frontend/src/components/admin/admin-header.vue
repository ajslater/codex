<template>
  <header id="adminHeader" :class="{ drawerMargin: !mdAndDown }">
    <AppBanner />
    <v-toolbar id="titleBar" flat density="compact">
      <span id="buttonSpacer" />
      <v-toolbar-title class="codexToolbarTitle">
        Codex Administration
      </v-toolbar-title>
      <SettingsDrawerButton
        :key="mdAndDown"
        class="adminSettingsButton"
        :class="{ invisible: !mdAndDown }"
        :disabled="!mdAndDown"
      />
    </v-toolbar>
    <v-tabs class="adminTabs" grow show-arrows>
      <v-tab
        v-for="tab in TABS"
        :key="tab"
        v-model="activeTab"
        :to="tab.toLowerCase()"
      >
        {{ tab }}
      </v-tab>
    </v-tabs>
  </header>
</template>
<script>
import { capitalCase } from "change-case-all";
import { mapWritableState } from "pinia";

import AppBanner from "@/components/banner.vue";
import SettingsDrawerButton from "@/components/settings/button.vue";
import { TABS, useAdminStore } from "@/stores/admin";
export default {
  name: "AdminTitleToolbar",
  components: {
    AppBanner,
    SettingsDrawerButton,
  },
  data() {
    return {
      TABS,
    };
  },
  computed: {
    ...mapWritableState(useAdminStore, ["activeTab"]),
    mdAndDown() {
      return this.$vuetify.display.mdAndDown;
    },
  },
  watch: {
    $route(to) {
      const parts = to.path.split("/");
      const lastPart = parts.at(-1);
      this.activeTab = capitalCase(lastPart);
    },
  },
};
</script>

<style scoped lang="scss">
#adminHeader {
  position: fixed;
  top: 0px;
  padding-top: env(safe-area-inset-top);
  z-index: 10;
  display: block;
  width: 100%;
}

.drawerMargin {
  width: calc(100% - 256px) !important;
}

.invisible {
  visibility: hidden;
}
#buttonSpacer {
  width: 48px;
}

#titleBar {
  padding-left: env(safe-area-inset-left);
  padding-right: 0px; // given to settings button.
}

.adminSettingsButton {
  margin: 0px !important;
}

.adminTabs {
  background-color: rgb(var(--v-theme-surface));
}

:deep(.tabHeader) {
  padding: 10px;
}
</style>

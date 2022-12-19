<template>
  <v-navigation-drawer
    v-model="isSettingsDrawerOpen"
    class="settingsDrawer"
    app
    location="right"
    touchless
    v-bind="$attrs"
  >
    <div class="settingsDrawerContainer">
      <div id="topBlock">
        <header class="settingsHeader">
          <h3>{{ title }}</h3>
        </header>
        <component :is="panel" v-if="isCodexViewable" />
        <v-divider />
        <SettingsCommonPanel :admin-menu="adminMenu" />
        <v-divider />
      </div>
      <div id="footerGroup">
        <SettingsFooter />
      </div>
    </div>
    <template #append>
      <VersionFooter />
    </template>
  </v-navigation-drawer>
</template>

<script>
import { mapGetters, mapWritableState } from "pinia";

import SettingsCommonPanel from "@/components/settings/panel.vue";
import SettingsFooter from "@/components/settings/settings-footer.vue";
import VersionFooter from "@/components/settings/version-footer.vue";
import { useAuthStore } from "@/stores/auth";
import { useCommonStore } from "@/stores/common";

export default {
  name: "SettingsDrawer",
  components: {
    SettingsCommonPanel,
    SettingsFooter,
    VersionFooter,
  },
  props: {
    title: {
      type: String,
      required: true,
    },
    panel: {
      type: Object,
      required: true,
    },
    adminMenu: {
      type: Boolean,
      default: true,
    },
  },
  computed: {
    ...mapGetters(useAuthStore, ["isCodexViewable"]),
    ...mapWritableState(useCommonStore, ["isSettingsDrawerOpen"]),
  },
  mounted() {
    if (this.adminMenu) {
      this.isSettingsDrawerOpen = !this.$vuetify.display.smAndDown;
    }
  },
};
</script>

<style scoped lang="scss">
.settingsDrawerContainer {
  position: relative !important;
  display: flex;
  flex-direction: column;
  justify-content: space-between;
  height: 100%;
  background-color: rgb(var(--v-theme-surface-dark));
}
.settingsHeader {
  padding: 10px;
  padding-left: 15px;
  background-color: rgb(var(--v-theme-on-surface-variant));
}
:deep(.v-list-item .v-icon) {
  color: rgb(var(--v-theme-iconsInactive)) !important;
  margin-right: 0.33em;
}
#footerGroup {
  background-color: rgb(var(--v-theme-surface));
}
</style>

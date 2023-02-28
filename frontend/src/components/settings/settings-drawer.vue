<template>
  <v-navigation-drawer
    v-bind="$attrs"
    v-model="isSettingsDrawerOpen"
    disable-resize-watcher
    disable-route-watcher
    location="right"
    :scrim="!adminAndNotSmall"
    :temporary="!adminAndNotSmall"
    touchless
  >
    <div class="settingsDrawerContainer">
      <div id="topBlock">
        <header class="settingsHeader">
          <h3>{{ title }}</h3>
        </header>
        <component :is="panel" v-if="isCodexViewable" />
        <v-divider v-if="isCodexViewable" />
        <SettingsCommonPanel :admin-menu="!admin" />
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
import { mapGetters, mapState, mapWritableState } from "pinia";

import SettingsCommonPanel from "@/components/settings/panel.vue";
import SettingsFooter from "@/components/settings/settings-footer.vue";
import VersionFooter from "@/components/settings/version-footer.vue";
import { useAuthStore } from "@/stores/auth";
import { useCommonStore } from "@/stores/common";
import { useReaderStore } from "@/stores/reader";

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
    admin: {
      type: Boolean,
      default: false,
    },
  },
  computed: {
    ...mapGetters(useAuthStore, ["isCodexViewable"]),
    ...mapWritableState(useCommonStore, ["isSettingsDrawerOpen"]),
    ...mapState(useReaderStore, {
      invisibleHack: (state) => state.bookChange === "next",
    }),
    adminAndNotSmall() {
      return this.admin && !this.$vuetify.display.smAndDown;
    },
  },
  mounted() {
    this.isSettingsDrawerOpen = this.adminAndNotSmall;
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
  background-color: rgb(var(--v-theme-background)) !important;
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

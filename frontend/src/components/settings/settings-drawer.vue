<template>
  <v-navigation-drawer
    v-model="open"
    disable-route-watcher
    location="right"
    touchless
  >
    <div class="settingsDrawerContainer">
      <div id="topBlock">
        <header class="settingsHeader">
          <h3>{{ title }}</h3>
        </header>
        <v-divider />
        <slot v-if="isAuthorized" name="panel" />
        <v-divider v-if="isAuthorized" />
        <AuthMenu />
        <component :is="AdminMenu" v-if="isUserAdmin" />
        <v-divider />
      </div>
      <div id="scrollFooter" class="footer">
        <OPDSDialog v-if="isAuthorized" />
        <DocsFooter />
      </div>
    </div>
    <template #append>
      <v-footer id="bottomFooter" class="footer">
        <VersionFooter />
      </v-footer>
    </template>
  </v-navigation-drawer>
</template>

<script>
import { mapActions, mapState } from "pinia";
import { defineAsyncComponent, markRaw } from "vue";

import AuthMenu from "@/components/auth/auth-menu.vue";
import DocsFooter from "@/components/settings/docs-footer.vue";
import OPDSDialog from "@/components/settings/opds-dialog.vue";
import VersionFooter from "@/components/settings/version-footer.vue";
import { useAuthStore } from "@/stores/auth";
import { useCommonStore } from "@/stores/common";
const AdminMenu = markRaw(
  defineAsyncComponent(
    () => import("@/components/admin/drawer/admin-menu.vue"),
  ),
);

export default {
  name: "SettingsDrawer",
  components: {
    AuthMenu,
    DocsFooter,
    OPDSDialog,
    VersionFooter,
  },
  props: {
    title: {
      type: String,
      required: true,
    },
  },
  data() {
    return {
      AdminMenu,
    };
  },
  computed: {
    ...mapState(useAuthStore, ["isUserAdmin", "isAuthorized"]),
    ...mapState(useCommonStore, {
      isSettingsDrawerOpen: (state) => state.isSettingsDrawerOpen,
    }),
    open: {
      get() {
        return this.isSettingsDrawerOpen || !this.isAuthorized;
      },
      set(value) {
        this.setSettingsDrawerOpen(value);
      },
    },
  },
  methods: {
    ...mapActions(useCommonStore, ["setSettingsDrawerOpen"]),
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
  background-color: rgb(var(--v-theme-surface-light));
}
#topBlock {
  background-color: rgb(var(--v-theme-background)) !important;
}
:deep(.v-list-item .v-icon) {
  color: rgb(var(--v-theme-iconsInactive)) !important;
  margin-right: 0.33em;
}
.footer {
  display: block;
  font-size: small;
  text-align: center;
  padding-top: 0px;
  background-color: rgb(var(--v-theme-surface));
  color: rgb(var(--v-theme-textDisabled));
}
#scrollFooter {
  padding-bottom: 0px;
}
#bottomFooter {
  padding-bottom: calc(5px + env(safe-area-inset-bottom) / 2);
}
</style>

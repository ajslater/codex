<template>
  <v-navigation-drawer
    v-model="isSettingsDrawerOpen"
    class="settingsDrawer"
    app
    location="right"
    touchless
    :mobile-breakpoint="960"
  >
    <div class="settingsDrawerContainer">
      <div id="topBlock">
        <AdminSettingsPanel />
        <v-divider />
        <SettingsCommonPanel :admin-menu="false" />
        <v-divider />
      </div>
      <div id="footerGroup">
        <DjangoAdminLink />
        <SettingsFooter />
      </div>
    </div>
    <template #append>
      <VersionFooter />
    </template>
  </v-navigation-drawer>
</template>

<script>
import { mapWritableState } from "pinia";

import AdminSettingsPanel from "@/components/admin/admin-settings-panel.vue";
import DjangoAdminLink from "@/components/admin/django-admin-link.vue";
import SettingsCommonPanel from "@/components/settings/panel.vue";
import SettingsFooter from "@/components/settings/settings-footer.vue";
import VersionFooter from "@/components/settings/version-footer.vue";
import { useAdminStore } from "@/stores/admin";

export default {
  name: "AdminSettingsDrawer",
  components: {
    AdminSettingsPanel,
    DjangoAdminLink,
    SettingsCommonPanel,
    SettingsFooter,
    VersionFooter,
  },
  computed: {
    ...mapWritableState(useAdminStore, ["isSettingsDrawerOpen"]),
  },
};
</script>

<style scoped lang="scss">
#footerGroup {
  background-color: rgb(var(--v-theme-surface));
}
</style>

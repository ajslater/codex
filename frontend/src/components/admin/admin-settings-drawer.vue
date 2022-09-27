<template>
  <v-navigation-drawer
    id="adminSetingsDrawer"
    v-model="isSettingsDrawerOpen"
    app
    right
    touchless
    :mobile-breakpoint="960"
  >
    <div id="settingsDrawerContainer">
      <div id="topBlock">
        <header id="adminMenuHeader">
          <h3>Admin Status</h3>
        </header>
        <v-list-item-group id="browserLink">
          <v-list-item ref="browserLink" ripple :to="browserRoute">
            <v-list-item-content>
              <v-list-item-title> Browser </v-list-item-title>
            </v-list-item-content>
          </v-list-item>
        </v-list-item-group>
        <v-divider />
        <SettingsCommonPanel :admin="false" />
      </div>
      <div id="footerGroup">
        <v-list-item-group>
          <v-list-item
            id="oldDjangoAdmin"
            :href="djangoAdminURL"
            target="_blank"
            ripple
          >
            <v-list-item-content>
              <v-list-item-title>
                Old Django Admin Panel
                <v-icon small>
                  {{ mdiOpenInNew }}
                </v-icon>
              </v-list-item-title>
            </v-list-item-content>
          </v-list-item>
        </v-list-item-group>
        <SettingsFooter />
      </div>
    </div>
    <template #append>
      <VersionFooter />
    </template>
  </v-navigation-drawer>
</template>

<script>
import { mdiOpenInNew } from "@mdi/js";
import { mapState, mapWritableState } from "pinia";

import SettingsCommonPanel from "@/components/settings/panel.vue";
import SettingsFooter from "@/components/settings/settings-footer.vue";
import VersionFooter from "@/components/settings/version-footer.vue";
import { useAdminStore } from "@/stores/admin";
import { useBrowserStore } from "@/stores/browser";

export default {
  name: "AdminSettingsDrawer",
  components: {
    SettingsCommonPanel,
    SettingsFooter,
    VersionFooter,
  },
  data() {
    return {
      djangoAdminURL: window.CODEX.DJANGO_ADMIN_PATH,
      mdiOpenInNew,
    };
  },
  computed: {
    ...mapWritableState(useAdminStore, ["isSettingsDrawerOpen"]),
    ...mapState(useBrowserStore, {
      browserRoute: (state) =>
        state.page.routes.last
          ? { name: "browser", params: state.page.routes.last }
          : { name: "home" },
    }),
  },
};
</script>

<style scoped lang="scss">
#adminSetingsDrawer {
  z-index: 20;
}
#adminMenuHeader {
  padding: 10px;
  padding-left: 15px;
}
@import "../settings/settings-drawer.scss";
#footerGroup {
  width: 100%;
  background-color: #272727;
  color: grey;
}
#oldDjangoAdmin:hover {
  color: white;
}
#oldDjangoAdmin {
  color: grey;
}
</style>

<!-- eslint-disable-next-line vue-scoped-css/enforce-style-type -->
<style lang="scss">
#oldDjangoAdmin .v-icon {
  color: grey;
}
#oldDjangoAdmin:hover .v-icon {
  color: white;
}
</style>

<template>
  <v-navigation-drawer
    id="adminSetingsDrawer"
    v-model="isSettingsDrawerOpen"
    app
    right
    touchless
    :mobile-breakpoint="1024"
  >
    <v-list-item-group id="browserLink">
      <v-list-item ref="browserLink" ripple :to="browserRoute">
        <v-list-item-content>
          <v-list-item-title> Browser </v-list-item-title>
        </v-list-item-content>
      </v-list-item>
    </v-list-item-group>
    <v-divider />
    <AuthMenu />
    <v-divider />
    <AdminStatusList />
    <v-divider />
    <v-list-item-group id="footerGroup">
      <v-divider />
      <v-list-item :href="djangoAdminURL" target="_blank" ripple>
        <v-list-item-content>
          <v-list-item-title id="oldDjangoTitle">
            Old Django Admin Panel
            <v-icon small>
              {{ mdiOpenInNew }}
            </v-icon>
          </v-list-item-title>
        </v-list-item-content>
      </v-list-item>
      <VersionFooter />
    </v-list-item-group>
  </v-navigation-drawer>
</template>

<script>
import { mdiOpenInNew } from "@mdi/js";
import { mapState, mapWritableState } from "pinia";

import AdminStatusList from "@/components/admin/status-list.vue";
import AuthMenu from "@/components/auth/auth-menu.vue";
import VersionFooter from "@/components/settings/version-footer.vue";
import { useAdminStore } from "@/stores/admin";
import { useBrowserStore } from "@/stores/browser";

export default {
  name: "AdminSettingsDrawer",
  components: {
    AdminStatusList,
    AuthMenu,
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
  padding-right: calc(env(safe-area-inset-right));
}
#footerGroup {
  color: grey;
  position: absolute;
  bottom: 0px;
  width: 100%;
}
#footerGroup:hover #oldDjangoTitle {
  color: white;
}
#oldDjangoTitle {
  color: grey;
}
</style>

<!-- eslint-disable-next-line vue-scoped-css/enforce-style-type -->
<style lang="scss">
#footerGroup:hover #oldDjangoTitle .v-icon {
  color: white;
}
#oldDjangoTitle .v-icon {
  color: grey;
}
</style>

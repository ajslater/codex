<template>
  <BrowserSettingsGroup />
  <BrowserSettingsCovers />
  <BrowserSettingsMisc />
</template>
<script>
import { mdiReload } from "@mdi/js";
import { mapState } from "pinia";

import { useAuthStore } from "@/stores/auth";

import BrowserSettingsCovers from "./browser-settings-covers.vue";
import BrowserSettingsGroup from "./browser-settings-group.vue";
import BrowserSettingsMisc from "./browser-settings-misc.vue";

export default {
  name: "BrowserSettingsPanel",
  components: {
    BrowserSettingsCovers,
    BrowserSettingsGroup,
    BrowserSettingsMisc,
  },
  data() {
    return {
      mdiReload,
    };
  },
  computed: {
    ...mapState(useAuthStore, ["isAuthorized"]),
    ...mapState(useAuthStore, {
      isUserAuthorized: (state) => Boolean(state.user),
    }),
  },
};
</script>
<style scoped lang="scss">
// settingsSubHeader defined in settings/settings-drawer.vue
</style>

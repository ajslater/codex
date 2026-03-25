<template>
  <BrowserSettingsGroup />
  <BrowserSettingsCovers />
  <BrowserSettingsMisc />
</template>
<script>
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
};
</script>
<style scoped lang="scss">
// settingsSubHeader defined in settings/settings-drawer.vue
</style>

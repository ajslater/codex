<template>
  <BrowserSettingsSaved />
  <BrowserSettingsCollection />
  <BrowserSettingsCovers />
  <BrowserSettingsMisc />
</template>
<script>
import BrowserSettingsCovers from "./browser-settings-covers.vue";
import BrowserSettingsCollection from "./browser-settings-collection.vue";
import BrowserSettingsMisc from "./browser-settings-misc.vue";
import BrowserSettingsSaved from "./browser-settings-saved.vue";

export default {
  name: "BrowserSettingsPanel",
  components: {
    BrowserSettingsCovers,
    BrowserSettingsCollection,
    BrowserSettingsMisc,
    BrowserSettingsSaved,
  },
};
</script>
<style scoped lang="scss">
// settingsSubHeader defined in settings/settings-drawer.vue
</style>

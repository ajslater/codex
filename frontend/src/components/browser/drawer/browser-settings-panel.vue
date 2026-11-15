<template>
  <BrowserSettingsSaved />
  <BrowserSettingsShelves />
  <BrowserSettingsCollection />
  <BrowserSettingsMisc />
</template>
<script>
import BrowserSettingsCollection from "./browser-settings-collection.vue";
import BrowserSettingsMisc from "./browser-settings-misc.vue";
import BrowserSettingsSaved from "./browser-settings-saved.vue";
import BrowserSettingsShelves from "./browser-settings-shelves.vue";

export default {
  name: "BrowserSettingsPanel",
  components: {
    BrowserSettingsCollection,
    BrowserSettingsMisc,
    BrowserSettingsSaved,
    BrowserSettingsShelves,
  },
};
</script>
<style scoped lang="scss">
// settingsSubHeader defined in styles/global.scss
</style>

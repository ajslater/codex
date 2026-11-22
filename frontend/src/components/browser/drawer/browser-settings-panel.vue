<template>
  <BrowserSettingsSaved />
  <BrowserSettingsReadingLists />
  <BrowserSettingsCollection />
  <BrowserSettingsMisc />
</template>
<script>
import BrowserSettingsCollection from "./browser-settings-collection.vue";
import BrowserSettingsMisc from "./browser-settings-misc.vue";
import BrowserSettingsReadingLists from "./browser-settings-reading-lists.vue";
import BrowserSettingsSaved from "./browser-settings-saved.vue";

export default {
  name: "BrowserSettingsPanel",
  components: {
    BrowserSettingsCollection,
    BrowserSettingsMisc,
    BrowserSettingsReadingLists,
    BrowserSettingsSaved,
  },
};
</script>
<style scoped lang="scss">
// settingsSubHeader defined in styles/global.scss
</style>

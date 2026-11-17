<template>
  <BrowserSettingsSaved />
  <BrowserSettingsShelves />
  <BrowserSettingsReadingLists />
  <BrowserSettingsCollection />
  <BrowserSettingsMisc />
</template>
<script>
import BrowserSettingsCollection from "./browser-settings-collection.vue";
import BrowserSettingsMisc from "./browser-settings-misc.vue";
import BrowserSettingsReadingLists from "./browser-settings-reading-lists.vue";
import BrowserSettingsSaved from "./browser-settings-saved.vue";
import BrowserSettingsShelves from "./browser-settings-shelves.vue";

export default {
  name: "BrowserSettingsPanel",
  components: {
    BrowserSettingsCollection,
    BrowserSettingsMisc,
    BrowserSettingsReadingLists,
    BrowserSettingsSaved,
    BrowserSettingsShelves,
  },
};
</script>
<style scoped lang="scss">
// settingsSubHeader defined in styles/global.scss
</style>

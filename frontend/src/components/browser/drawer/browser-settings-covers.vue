<!--
  PENDING SCHEMA REMOVAL

  Parked, not live. Nothing imports this component, so it never enters the
  bundle -- it is kept intact so the two cover options can be put back by
  restoring one line in browser-settings-panel.vue.

  Dynamic covers and custom covers are both pinned on; see the notes in
  views/browser/annotate/cover.py and models/settings.py. Their
  SettingsBrowser columns and serializer fields are still there, so the
  checkboxes below would bind to real stored values on the day they come
  back. Delete this file when the columns go.
-->
<template>
  <div class="browserSettingsBlock">
    <div class="settingsSubHeader">Covers</div>
    <v-checkbox
      v-tooltip="{
        openDelay,
        text: 'Choose covers by filters, search, and order',
      }"
      class="browserCollectionCheckbox"
      density="compact"
      hide-details="auto"
      :model-value="dynamicCovers"
      :true-value="true"
      label="Dynamic Covers"
      @update:model-value="setSetting('dynamicCovers', $event)"
    />
    <v-checkbox
      v-tooltip="{
        openDelay,
        text: 'Overlay custom covers if the admin has set them.',
      }"
      class="browserCollectionCheckbox"
      density="compact"
      hide-details="auto"
      :model-value="customCovers"
      :true-value="true"
      label="Custom Covers"
      @update:model-value="setSetting('customCovers', $event)"
    />
  </div>
  <v-divider />
</template>
<script>
import { mapActions, mapState } from "pinia";

import { useBrowserStore } from "@/stores/browser";

export default {
  name: "BrowserSettingsCovers",
  data() {
    return {
      openDelay: 2000,
    };
  },
  computed: {
    ...mapState(useBrowserStore, {
      dynamicCovers: (state) => state.settings?.dynamicCovers || false,
      customCovers: (state) => state.settings?.customCovers || false,
    }),
  },
  methods: {
    ...mapActions(useBrowserStore, ["setSettings"]),
    setSetting(key, value) {
      const data = { [key]: value === true };
      this.setSettings(data);
    },
  },
};
</script>
<style scoped lang="scss">
.browserCollectionCheckbox {
  padding-right: 10px;
  padding-left: 15px;
}
</style>

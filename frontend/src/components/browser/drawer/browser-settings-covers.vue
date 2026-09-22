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
    <v-checkbox
      v-tooltip="{
        openDelay,
        text: 'Mark read, unread and in progress state under each cover.',
      }"
      class="browserCollectionCheckbox"
      density="compact"
      hide-details="auto"
      :model-value="showReadState"
      :true-value="true"
      label="Read State"
      @update:model-value="setSetting('showReadState', $event)"
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
      // Defaults on, so ``!== false`` rather than ``|| false``.
      showReadState: (state) => state.settings?.showReadState !== false,
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

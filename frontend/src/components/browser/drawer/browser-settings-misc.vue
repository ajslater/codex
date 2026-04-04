<template>
  <v-checkbox
    v-tooltip="{
      openDelay: 1000,
      text: 'Always show filenames on the browser cards',
    }"
    class="browserGroupCheckbox"
    density="compact"
    label="Always Show Filenames"
    hide-details="auto"
    :model-value="Boolean(alwaysShowFilename)"
    @update:model-value="setSetting('alwaysShowFilename', $event)"
  />
  <v-checkbox
    class="browserGroupCheckbox"
    density="compact"
    hide-details="auto"
    :model-value="twentyFourHourTime"
    :true-value="true"
    indeterminate
    label="Force 24 Hour Time"
    @update:model-value="setSetting('twentyFourHourTime', $event)"
  />
  <v-divider />
</template>
<script>
import { mapActions, mapState } from "pinia";

import { useBrowserStore } from "@/stores/browser";

export default {
  name: "BrowserSettingsMisc",
  computed: {
    ...mapState(useBrowserStore, {
      twentyFourHourTime: (state) =>
        state.settings?.twentyFourHourTime || false,
      twentyFourHourTimeTitle: (state) =>
        state.choices?.static?.twentyFourHourTime?.title || "",
      alwaysShowFilename: (state) =>
        state.settings?.alwaysShowFilename || false,
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
.browserGroupCheckbox {
  padding-right: 10px;
  padding-left: 15px;
}
</style>

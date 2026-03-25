<template>
  <div
    v-if="showShowSettings"
    v-tooltip="{
      openDelay,
      text: 'Show these groups when navigating the browse tree',
    }"
    class="browserSettingsBlock"
  >
    <div class="settingsSubHeader">Show Group Levels</div>
    <v-checkbox
      v-for="choice of groupChoices"
      :key="choice.title"
      class="browserGroupCheckbox"
      density="compact"
      hide-details="auto"
      :model-value="showSettings[choice.value]"
      :true-value="true"
      :label="`Show ${choice.title}`"
      @update:model-value="setShow(choice.value, $event)"
    />
  </div>
  <v-divider />
</template>
<script>
import { mapActions, mapState } from "pinia";

import { useBrowserStore } from "@/stores/browser";
const SHOW_SETTINGS_GROUPS = "rpisv";

export default {
  name: "BrowserSettingsGroup",
  data() {
    return {
      openDelay: 2000,
    };
  },
  computed: {
    ...mapState(useBrowserStore, {
      groupChoices: (state) => state.choices?.static?.settingsGroup || {},
      showSettings: (state) => state.settings?.show || {},
    }),
    showShowSettings() {
      return SHOW_SETTINGS_GROUPS.includes(this.$route?.params?.group);
    },
  },
  methods: {
    ...mapActions(useBrowserStore, ["setSettings"]),
    setShow(group, value) {
      const data = { show: { [group]: value === true } };
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

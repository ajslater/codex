<template>
  <header class="settingsHeader">
    <h3>Browser Settings</h3>
  </header>
  <div id="browserSettings">
    <div id="groupCaption" class="text-caption">
      Show these groups when navigating the browse tree.
    </div>
    <v-checkbox
      v-for="choice of groupChoices"
      :key="choice.title"
      :model-value="showSettings[choice.value]"
      :true-value="true"
      :label="`Show ${choice.title}`"
      density="compact"
      hide-details="auto"
      class="browserGroupCheckbox"
      @update:modelValue="setShow(choice.value, $event)"
    />
  </div>
</template>
<script>
import { mapActions, mapState } from "pinia";

import { useBrowserStore } from "@/stores/browser";

export default {
  name: "BrowserSettingsPanel",
  computed: {
    ...mapState(useBrowserStore, {
      groupChoices: (state) => state.choices.static.settingsGroup,
      showSettings: (state) => state.settings.show,
    }),
  },
  methods: {
    ...mapActions(useBrowserStore, ["setSettings"]),
    setShow: function (group, value) {
      const data = { show: { [group]: value === true } };
      this.setSettings(data);
    },
  },
};
</script>
<style scoped lang="scss">
#browserSettings {
  padding: 10px;
  padding-left: 15px;
}
#groupCaption {
  color: rgb(var(--v-theme-textDisabled));
}
</style>
<style lang="scss">
/* v-navigation drawer imparts a lot of nonsense here messing up colors */
#browserSettings .browserGroupCheckbox .v-label {
  opacity: 1.2 !important;
}
</style>

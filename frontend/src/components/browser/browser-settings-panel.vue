<template>
  <div id="browserSettings" title="">
    <h3>Browser Settings</h3>
    <div id="settingsGroupCaption" class="text-caption">
      Show these groups when navigating the browse tree.
    </div>
    <v-checkbox
      v-for="choice of groupChoices"
      :key="choice.text"
      :input-value="showSettings[choice.value]"
      :label="`Show ${choice.text}`"
      density="compact"
      class="settingsCheckbox"
      @change="setShow(choice.value, $event)"
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
  padding-top: 10px;
  padding-left: 15px;
  padding-right: env(safe-area-inset-right);
}
#settingsGroupCaption {
  padding-top: 10px;
  color: gray;
}
.settingsCheckbox {
  padding-left: 5px;
}
</style>

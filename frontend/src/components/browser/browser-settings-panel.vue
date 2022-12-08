<template>
  <div v-if="isCodexViewable" id="browserSettings">
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
    <v-divider />
    <SearchHelp />
  </div>
</template>
<script>
import { mapActions, mapGetters, mapState } from "pinia";

import SearchHelp from "@/components/browser/search-help.vue";
import { useAuthStore } from "@/stores/auth";
import { useBrowserStore } from "@/stores/browser";

export default {
  name: "BrowserSettingsPanel",
  components: {
    SearchHelp,
  },
  computed: {
    ...mapGetters(useAuthStore, ["isCodexViewable"]),
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

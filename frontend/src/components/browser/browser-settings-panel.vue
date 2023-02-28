<template>
  <div id="groupCaption" class="text-caption">
    Show these groups when navigating the browse tree.
  </div>
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
  <v-divider />
  <v-checkbox
    class="browserGroupCheckbox"
    density="compact"
    hide-details="auto"
    :model-value="twentyFourHourTime"
    :true-value="true"
    label="24 Hour Time"
    @update:model-value="set24HourTime($event)"
  />
  <v-divider />
  <SearchHelp />
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
      twentyFourHourTimeTitle: (state) =>
        state.choices.static.twentyFourHourTime.title,
      showSettings: (state) => state.settings.show,
      twentyFourHourTime: (state) => state.settings.twentyFourHourTime,
    }),
  },
  methods: {
    ...mapActions(useBrowserStore, ["setSettings"]),
    setShow(group, value) {
      const data = { show: { [group]: value === true } };
      this.setSettings(data);
    },
    set24HourTime(value) {
      const data = { twentyFourHourTime: value === true };
      this.setSettings(data);
    },
  },
};
</script>
<style scoped lang="scss">
#groupCaption,
.browserGroupCheckbox {
  padding-right: 10px;
  padding-left: 15px;
}
#groupCaption {
  padding-top: 10px;
  color: rgb(var(--v-theme-textDisabled));
}
</style>

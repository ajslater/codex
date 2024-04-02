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
  <v-radio-group
    class="searchResultsRadioGroup"
    density="compact"
    label="Search Results Limit"
    hide-details="auto"
    :model-value="searchResultsLimit"
    @update:model-value="setSearchResultsLimit($event)"
  >
    <v-radio
      v-for="item in SEARCH_LIMIT_CHOICES"
      :key="item.value"
      class="searchResultsRadio"
      :label="item.title"
      :value="item.value"
    />
  </v-radio-group>
  <SearchHelp />
  <v-divider />
  <v-checkbox
    class="browserGroupCheckbox"
    density="compact"
    hide-details="auto"
    :model-value="twentyFourHourTime"
    :true-value="true"
    indeterminate
    label="Force 24 Hour Time"
    @update:model-value="set24HourTime($event)"
  />
</template>
<script>
import { mapActions, mapGetters, mapState } from "pinia";

import SearchHelp from "@/components/browser/drawer/search-help.vue";
import { useAuthStore } from "@/stores/auth";
import { useBrowserStore } from "@/stores/browser";

const SEARCH_LIMIT_CHOICES = [
  { value: 10, title: "10" },
  { value: 100, title: "100 (one page)" },
  { value: 0, title: "Unlimited" },
];

export default {
  name: "BrowserSettingsPanel",
  components: {
    SearchHelp,
  },
  data() {
    return {
      SEARCH_LIMIT_CHOICES,
    };
  },
  computed: {
    ...mapGetters(useAuthStore, ["isCodexViewable"]),
    ...mapState(useBrowserStore, {
      groupChoices: (state) => state.choices.static.settingsGroup,
      searchResultsLimit: (state) => state.settings.searchResultsLimit,
      showSettings: (state) => state.settings.show,
      twentyFourHourTime: (state) => state.settings.twentyFourHourTime,
      twentyFourHourTimeTitle: (state) =>
        state.choices.static.twentyFourHourTime.title,
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
    setSearchResultsLimit(value) {
      const data = { searchResultsLimit: value || 0 };
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
.searchResultsRadioGroup {
  margin-top: 10px;
}
.searchResultsRadio {
  padding-left: 8px
}
</style>

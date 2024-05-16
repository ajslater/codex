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
  <!--
  <v-checkbox
    v-tooltip="{
      openDelay: 1000,
      text: 'Speed up search results by searching one page at a time',
    }"
    class="searchResultsCheckbox"
    density="compact"
    label="Incremental Search"
    hide-details="auto"
    :model-value="Boolean(searchResultsLimit)"
    @update:model-value="setSearchResultsLimit($event)"
  />
  -->
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

export default {
  name: "BrowserSettingsPanel",
  components: {
    SearchHelp,
  },
  computed: {
    ...mapGetters(useAuthStore, ["isAuthorized"]),
    ...mapState(useAuthStore, {
      isUserAuthorized: (state) => Boolean(state.user),
    }),
    ...mapState(useBrowserStore, {
      groupChoices: (state) => state.choices?.static?.settingsGroup || {},
      // searchResultsLimit: (state) => state.settings?.searchResultsLimit || 100,
      showSettings: (state) => state.settings?.show || {},
      twentyFourHourTime: (state) =>
        state.settings?.twentyFourHourTime || false,
      twentyFourHourTimeTitle: (state) =>
        state.choices?.static?.twentyFourHourTime?.title || "",
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
    /*
    setSearchResultsLimit(value) {
      const searchResultsLimit = value ? 100 : 0;
      const data = { searchResultsLimit };
      this.setSettings(data);
    },
    */
  },
};
</script>
<style scoped lang="scss">
#groupCaption,
.browserGroupCheckbox,
// .searchResultsCheckbox
{
  padding-right: 10px;
  padding-left: 15px;
}
#groupCaption {
  padding-top: 10px;
  color: rgb(var(--v-theme-textDisabled));
}
</style>

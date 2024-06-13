<template>
  <div
    v-if="showShowSettings"
    id="showSettings"
    v-tooltip="{
      openDelay,
      text: 'Show these groups when navigating the browse tree',
    }"
  >
    <h4 class="settingsHeader">Show Group Levels</h4>
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
  <div>
    <h4 class="settingsHeader">Covers</h4>
    <v-checkbox
      v-tooltip="{
        openDelay,
        text: 'Choose covers by filters, search, and order',
      }"
      class="browserGroupCheckbox"
      density="compact"
      hide-details="auto"
      :model-value="dynamicCovers"
      :true-value="true"
      label="Dynamic Covers"
      @update:model-value="setDynamicCovers($event)"
    />
    <v-checkbox
      v-tooltip="{
        openDelay,
        text: 'Overlay custom covers if the admin has set them.',
      }"
      class="browserGroupCheckbox"
      density="compact"
      hide-details="auto"
      :model-value="customCovers"
      :true-value="true"
      label="Custom Covers"
      @update:model-value="setCustomCovers($event)"
    />
  </div>
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
  <v-divider />
  <DrawerItem
    :prepend-icon="mdiReload"
    title="Refresh"
    @click.stop="onRefresh"
  />
</template>
<script>
import { mdiReload } from "@mdi/js";
import { mapActions, mapGetters, mapState } from "pinia";

import SearchHelp from "@/components/browser/drawer/search-help.vue";
import DrawerItem from "@/components/drawer-item.vue";
import { useAuthStore } from "@/stores/auth";
import { useBrowserStore } from "@/stores/browser";
const SHOW_SETTINGS_GROUPS = "rpisv";

export default {
  name: "BrowserSettingsPanel",
  components: {
    SearchHelp,
    DrawerItem,
  },
  data() {
    return {
      mdiReload,
      openDelay: 2000, // for tooltips
    };
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
      dynamicCovers: (state) => state.settings?.dynamicCovers || false,
      customCovers: (state) => state.settings?.customCovers || false,
    }),
    showShowSettings() {
      return SHOW_SETTINGS_GROUPS.includes(this.$route?.params?.group);
    },
  },
  methods: {
    ...mapActions(useBrowserStore, ["loadMtimes", "setSettings"]),
    setShow(group, value) {
      const data = { show: { [group]: value === true } };
      this.setSettings(data);
    },
    set24HourTime(value) {
      const data = { twentyFourHourTime: value === true };
      this.setSettings(data);
    },
    setDynamicCovers(value) {
      const data = { dynamicCovers: value === true };
      this.setSettings(data);
    },
    setCustomCovers(value) {
      const data = { customCovers: value === true };
      this.setSettings(data);
    },
    /*
    setSearchResultsLimit(value) {
      const searchResultsLimit = value ? 100 : 0;
      const data = { searchResultsLimit };
      this.setSettings(data);
    },
    */
    onRefresh() {
      this.loadMtimes();
    },
  },
};
</script>
<style scoped lang="scss">
#showSettings{
  padding-top: 10px;
}
.browserGroupCheckbox,
.settingsHeader,
// .searchResultsCheckbox
{
  padding-right: 10px;
  padding-left: 15px;
}
.settingsHeader {
  color: rgb(var(--v-theme-textDisabled));
}
</style>

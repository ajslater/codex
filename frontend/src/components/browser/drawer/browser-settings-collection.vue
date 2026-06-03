<template>
  <div
    v-if="showShowSettings"
    v-tooltip="{
      openDelay,
      text: 'Show these collections when navigating the browse tree',
    }"
    class="browserSettingsBlock"
  >
    <div class="settingsSubHeader">Show Collection Levels</div>
    <v-checkbox
      v-for="choice of collectionChoices"
      :key="choice.title"
      class="browserCollectionCheckbox"
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
// Collections whose route shows the collection-level toggles. Root browses as the
// publishers collection, so "publishers" covers both root and publishers;
// comics / folders / arcs routes hide the toggles.
const SHOW_SETTINGS_COLLECTIONS = Object.freeze(
  new Set(["publishers", "imprints", "series", "volumes"]),
);

export default {
  name: "BrowserSettingsCollection",
  data() {
    return {
      openDelay: 2000,
    };
  },
  computed: {
    ...mapState(useBrowserStore, {
      collectionChoices: (state) =>
        state.choices?.static?.settingsCollection || {},
      showSettings: (state) => state.settings?.show || {},
    }),
    showShowSettings() {
      return SHOW_SETTINGS_COLLECTIONS.has(this.$route?.params?.collection);
    },
  },
  methods: {
    ...mapActions(useBrowserStore, ["setSettings"]),
    setShow(collection, value) {
      const data = { show: { [collection]: value === true } };
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

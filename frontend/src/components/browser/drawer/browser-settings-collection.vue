<template>
  <div
    v-if="showShowSettings"
    v-tooltip="{
      openDelay,
      text: 'Show these collections when navigating the browse tree',
    }"
    class="browserSettingsBlock"
  >
    <v-checkbox-group
      :model-value="shownCollections"
      density="compact"
      hide-details
      class="browserCollectionGroup"
      @update:model-value="onShownUpdate"
    >
      <template #label>
        <div class="settingsSubHeader">Show Collection Levels</div>
      </template>
      <v-checkbox
        v-for="choice of collectionChoices"
        :key="choice.title"
        class="browserCollectionCheckbox"
        :value="choice.value"
        :label="`Show ${choice.title}`"
      />
    </v-checkbox-group>
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
        state.choices?.static?.settingsCollection || [],
      showSettings: (state) => state.settings?.show || {},
    }),
    shownCollections() {
      return this.collectionChoices
        .filter(({ value }) => this.showSettings[value])
        .map(({ value }) => value);
    },
    showShowSettings() {
      return SHOW_SETTINGS_COLLECTIONS.has(this.$route?.params?.collection);
    },
  },
  methods: {
    ...mapActions(useBrowserStore, ["setSettings"]),
    onShownUpdate(shown) {
      // The group reports the whole list; send only the flag a click flipped,
      // since every settings change reloads the browser page.
      const changed = this.collectionChoices.find(
        ({ value }) =>
          shown.includes(value) !== this.shownCollections.includes(value),
      );
      if (changed) {
        this.setShow(changed.value, shown.includes(changed.value));
      }
    },
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

/*
 * The sub-header is the group's label. Undo the label's dimming and its
 * gap above the boxes so it and the checkboxes sit where they did before.
 */
@layer codex-components {
  .browserCollectionGroup :deep(> .v-input__control > .v-label) {
    opacity: 1;
  }

  .browserCollectionGroup
    :deep(> .v-input__control > .v-label + .v-selection-control-group) {
    margin-block-start: 0;
  }
}
</style>

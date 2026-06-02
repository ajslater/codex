<template>
  <ToolbarSelect
    v-model="topCollection"
    class="topGroupSelect"
    select-label="top collection"
    :items="topCollectionChoicesWithDividers"
    :max-select-len="topCollectionChoicesMaxLen - 2.25"
  >
    <template #item="{ internalItem, props }">
      <v-list-item
        v-bind="props"
        density="compact"
        variant="plain"
        :title="internalItem.title"
        :value="internalItem.value"
      />
    </template>
  </ToolbarSelect>
</template>

<script>
import { mapActions, mapState } from "pinia";

import ToolbarSelect from "@/components/toolbar-select.vue";
import { useBrowserStore } from "@/stores/browser";

const DIVIDED_VALUES = new Set(["arcs", "folders"]);

export default {
  name: "BrowserTopCollectionSelect",
  components: {
    ToolbarSelect,
  },
  extends: ToolbarSelect,
  data() {
    return {
      DIVIDED_VALUES,
    };
  },
  computed: {
    ...mapState(useBrowserStore, {
      topGroupSetting: (state) => state.settings.topCollection,
    }),
    ...mapState(useBrowserStore, [
      "topCollectionChoices",
      "topCollectionChoicesMaxLen",
    ]),
    topCollection: {
      get() {
        return this.topGroupSetting;
      },
      set(value) {
        const settings = { topCollection: value };
        this.setSettings(settings);
      },
    },
    topCollectionChoicesWithDividers() {
      const items = [];
      for (const item of this.topCollectionChoices) {
        if (DIVIDED_VALUES.has(item.value)) {
          items.push({ type: "divider" });
        }
        items.push(item);
      }
      return items;
    },
  },
  methods: {
    ...mapActions(useBrowserStore, ["setSettings"]),
  },
};
</script>

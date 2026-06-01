<template>
  <ToolbarSelect
    v-model="topCollection"
    class="topGroupSelect"
    select-label="top group"
    :items="topGroupChoicesWithDividers"
    :max-select-len="topGroupChoicesMaxLen - 2.25"
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
  name: "BrowserTopGroupSelect",
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
    ...mapState(useBrowserStore, ["topGroupChoices", "topGroupChoicesMaxLen"]),
    topCollection: {
      get() {
        return this.topGroupSetting;
      },
      set(value) {
        const settings = { topCollection: value };
        this.setSettings(settings);
      },
    },
    topGroupChoicesWithDividers() {
      const items = [];
      for (const item of this.topGroupChoices) {
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

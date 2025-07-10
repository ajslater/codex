<template>
  <ToolbarSelect
    v-model="topGroup"
    class="topGroupSelect"
    select-label="top group"
    :items="topGroupChoicesWithDividers"
    :max-select-len="topGroupChoicesMaxLen - 2.25"
  >
    <template #item="{ item, props }">
      <v-list-item
        v-bind="props"
        density="compact"
        variant="plain"
        :title="item.title"
        :value="item.value"
      />
    </template>
  </ToolbarSelect>
</template>

<script>
import { mapActions, mapState } from "pinia";

import ToolbarSelect from "@/components/toolbar-select.vue";
import { useBrowserStore } from "@/stores/browser";

const DIVIDED_VALUES = new Set(["a", "f"]);

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
      topGroupSetting: (state) => state.settings.topGroup,
    }),
    ...mapState(useBrowserStore, ["topGroupChoices", "topGroupChoicesMaxLen"]),
    topGroup: {
      get() {
        return this.topGroupSetting;
      },
      set(value) {
        const settings = { topGroup: value };
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

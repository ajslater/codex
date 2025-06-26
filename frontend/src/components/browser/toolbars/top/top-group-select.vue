<template>
  <ToolbarSelect
    v-model="topGroup"
    class="topGroupSelect"
    select-label="top group"
    :items="topGroupChoices"
    :max-select-len="topGroupChoicesMaxLen - 2.25"
  >
    <template #item="{ item, props }">
      <!-- Divider in items not implemented yet in Vuetify 3 -->
      <v-divider v-if="DIVIDED_VALUES.has(item.value)" />
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
  },
  methods: {
    ...mapActions(useBrowserStore, ["setSettings"]),
  },
};
</script>

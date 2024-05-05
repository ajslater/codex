<template>
  <ToolbarSelect
    v-model="orderBy"
    class="orderBySelect"
    select-label="order by"
    :items="orderByChoices"
    :max-select-len="orderByChoicesMaxLen - 4"
    v-bind="$attrs"
  />
</template>

<script>
import { mapActions, mapGetters, mapState } from "pinia";

import ToolbarSelect from "@/components/browser/toolbars/toolbar-select.vue";
import { useBrowserStore } from "@/stores/browser";

export default {
  name: "BrowseOrderBySelect",
  components: {
    ToolbarSelect,
  },
  extends: ToolbarSelect,
  computed: {
    ...mapGetters(useBrowserStore, ["orderByChoices", "orderByChoicesMaxLen"]),
    ...mapState(useBrowserStore, {
      orderBySetting: (state) => state.settings.orderBy,
    }),
    reverseValues() {
      const set = new Set();
      for (const choice of this.orderByChoices) {
        if (choice.reverse) {
          set.add(choice.value);
        }
      }
      return set;
    },
    orderBy: {
      get() {
        return this.orderBySetting;
      },
      set(value) {
        const data = {
          orderBy: value,
          orderReverse: this.reverseValues.has(value),
        };
        this.setSettings(data);
      },
    },
  },
  methods: {
    ...mapActions(useBrowserStore, ["setSettings"]),
  },
};
</script>

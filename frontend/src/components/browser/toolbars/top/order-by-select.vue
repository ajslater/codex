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
import { mapActions, mapState } from "pinia";

import ToolbarSelect from "@/components/toolbar-select.vue";
import { useBrowserStore } from "@/stores/browser";

const REVERSE_BY_DEFAULT = new Set([
  "bookmark_updated_at",
  "child_count",
  "created_at",
  "critical_rating",
  "page_count",
  "search_score",
  "size",
  "updated_at",
]);

export default {
  name: "BrowseOrderBySelect",
  components: {
    ToolbarSelect,
  },
  extends: ToolbarSelect,
  computed: {
    ...mapState(useBrowserStore, ["orderByChoices", "orderByChoicesMaxLen"]),
    ...mapState(useBrowserStore, {
      orderBySetting: (state) => state.settings.orderBy,
    }),
    orderBy: {
      get() {
        return this.orderBySetting;
      },
      set(value) {
        const data = {
          orderBy: value,
          orderReverse: REVERSE_BY_DEFAULT.has(value),
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

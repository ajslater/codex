<template>
  <ToolbarSelect
    v-model="orderBy"
    class="orderBySelect"
    select-label="order by"
    :items="orderByChoices"
    :max-select-len="orderByChoicesMaxLen - 3.5"
    :mobile-len-adj="-2"
    v-bind="$attrs"
  />
</template>

<script>
import { mapActions, mapGetters, mapState } from "pinia";

import ToolbarSelect from "@/components/browser/toolbar-select.vue";
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
    orderBy: {
      get() {
        return this.orderBySetting;
      },
      set(value) {
        const data = { orderBy: value };
        this.setSettings(data);
      },
    },
  },
  methods: {
    ...mapActions(useBrowserStore, ["setSettings"]),
  },
};
</script>

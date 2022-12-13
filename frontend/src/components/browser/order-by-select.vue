<template>
  <ToolbarSelect
    v-model="orderBy"
    class="orderBySelect"
    select-label="order by"
    :append-icon="orderIcon"
    :items="orderByChoices"
    :style="style"
    v-bind="$attrs"
    @click:append="toggleOrderReverse"
  />
</template>

<script>
import { mdiSortReverseVariant, mdiSortVariant } from "@mdi/js";
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
      orderReverseSetting: (state) => state.settings.orderReverse,
      orderBySetting: (state) => state.settings.orderBy,
      orderIcon: (state) =>
        state.settings.orderReverse ? mdiSortVariant : mdiSortReverseVariant,
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
    style() {
      const len = this.orderByChoicesMaxLen - 1 + "em";
      return `width: ${len}; min-width: ${len}; max-width: ${len}`;
    },
  },
  methods: {
    ...mapActions(useBrowserStore, ["setSettings"]),
    toggleOrderReverse: function () {
      const data = { orderReverse: !this.orderReverseSetting };
      this.setSettings(data);
    },
  },
};
</script>

<!-- eslint-disable-next-line vue-scoped-css/enforce-style-type -->
<style scoped lang="scss">
.orderIcon {
  float: right;
  margin-left: 5px;
}
/* #orderSelect style is handled in browser/filter-toolbar.vue */
</style>

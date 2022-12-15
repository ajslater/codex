<template>
  <ToolbarSelect
    v-model="orderBy"
    class="orderBySelect"
    select-label="order by"
    :items="orderByChoices"
    :style="style"
    v-bind="$attrs"
    @click:append="toggleOrderReverse"
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
    style() {
      const adj = this.$vuetify.display.mobile ? -5.5 : -3;
      const val = this.orderByChoicesMaxLen + adj;
      return this.emStyle(val);
    },
  },
  methods: {
    ...mapActions(useBrowserStore, ["setSettings", "emStyle"]),
  },
};
</script>

<style scoped lang="scss">
/* #orderSelect style is handled in browser/filter-toolbar.vue */
</style>

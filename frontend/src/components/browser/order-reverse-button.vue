<template>
  <v-btn
    class="orderReverseButton"
    icon
    height="46"
    variant="flat"
    v-bind="$attrs"
    @click="toggleOrderReverse"
  >
    <v-icon>{{ orderIcon }}</v-icon>
  </v-btn>
</template>

<script>
import { mdiSortReverseVariant, mdiSortVariant } from "@mdi/js";
import { mapActions, mapState } from "pinia";

import { useBrowserStore } from "@/stores/browser";

export default {
  name: "BrowseOrderReverseButton",
  computed: {
    ...mapState(useBrowserStore, {
      orderReverseSetting: (state) => state.settings.orderReverse,
      orderIcon: (state) =>
        state.settings.orderReverse ? mdiSortVariant : mdiSortReverseVariant,
    }),
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

<style scoped lang="scss">
/* #orderSelect style is handled in browser/filter-toolbar.vue */
</style>

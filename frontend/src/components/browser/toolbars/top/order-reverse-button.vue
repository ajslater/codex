<template>
  <ToolbarButton
    class="orderReverseButton"
    icon
    :title="title"
    @click="toggleOrderReverse"
  >
    <v-icon :class="iconClasses">
      {{ mdiSortVariant }}
    </v-icon>
  </ToolbarButton>
</template>

<script>
import { mdiSortVariant } from "@mdi/js";
import { mapActions, mapState } from "pinia";

import ToolbarButton from "@/components/browser/toolbars/top/toolbar-button.vue";
import { useBrowserStore } from "@/stores/browser";

export default {
  name: "BrowseOrderReverseButton",
  components: {
    ToolbarButton,
  },
  data() {
    return {
      mdiSortVariant,
    };
  },
  computed: {
    ...mapState(useBrowserStore, {
      orderReverseSetting: (state) => state.settings.orderReverse,
    }),
    title() {
      return this.orderReverseSetting ? "order descending" : "order ascending";
    },
    iconClasses() {
      return {
        inverted: !this.orderReverseSetting,
      };
    },
  },
  methods: {
    ...mapActions(useBrowserStore, ["setSettings"]),
    toggleOrderReverse() {
      const data = { orderReverse: !this.orderReverseSetting };
      this.setSettings(data);
    },
  },
};
</script>

<style scoped lang="scss">
.inverted {
  transform: scale(1, -1);
}
</style>

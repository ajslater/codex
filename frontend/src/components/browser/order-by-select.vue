<template>
  <div>
    <v-hover v-slot="{ hover }">
      <v-select
        v-model="orderBy"
        class="toolbarSelect orderBySelect"
        :append-outer-icon="orderIcon"
        density="compact"
        hide-details="auto"
        :items="orderByChoices"
        :label="focused || hover ? label : undefined"
        :menu-props="{
          maxHeight: '80vh',
          overflowY: false,
        }"
        @click:append-outer="toggleOrderReverse"
        @focus="focused = true"
        @blur="focused = false"
      >
        <template #item="data">
          <v-list-item v-bind="data.attrs">
            <v-list-item-title>
              {{ data.item.title }}
              <v-icon v-show="orderBy === data.item.value" class="orderIcon">
                {{ orderIcon }}
              </v-icon>
            </v-list-item-title>
          </v-list-item>
        </template>
      </v-select>
    </v-hover>
  </div>
</template>

<script>
import { mdiSortReverseVariant, mdiSortVariant } from "@mdi/js";
import { mapActions, mapGetters, mapState } from "pinia";

import { useBrowserStore } from "@/stores/browser";

export default {
  name: "BrowseOrderBySelect",
  data() {
    return {
      focused: false,
      mdiSortVariant,
      label: "order by",
    };
  },
  computed: {
    ...mapState(useBrowserStore, {
      orderReverseSetting: (state) => state.settings.orderReverse,
      orderBySetting: (state) => state.settings.orderBy,
      orderIcon: (state) =>
        state.settings.orderReverse ? mdiSortVariant : mdiSortReverseVariant,
    }),
    ...mapGetters(useBrowserStore, ["orderByChoices"]),
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

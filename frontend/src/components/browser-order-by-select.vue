<template>
  <v-hover v-slot="{ hover }">
    <v-select
      v-model="orderBy"
      class="toolbarSelect orderBySelect"
      :append-outer-icon="orderIcon"
      dense
      hide-details="auto"
      :items="orderChoices"
      :label="focused || hover ? label : undefined"
      :menu-props="{
        maxHeight: '80vh',
        overflowY: false,
      }"
      ripple
      @click:append-outer="toggleOrderReverse"
      @focus="focused = true"
      @blur="focused = false"
    >
      <template #item="data">
        <v-list-item v-bind="data.attrs" v-on="data.on">
          <v-list-item-content>
            <v-list-item-title>
              {{ data.item.text }}
              <v-icon v-show="orderBy === data.item.value" class="orderIcon">
                {{ orderIcon }}
              </v-icon>
            </v-list-item-title>
          </v-list-item-content>
        </v-list-item>
      </template>
    </v-select>
  </v-hover>
</template>

<script>
import { mdiSortReverseVariant, mdiSortVariant } from "@mdi/js";
import { mapState } from "vuex";

export default {
  name: "BrowseSortBySelect",
  data() {
    return {
      focused: false,
      mdiSortVariant,
      label: "order by",
    };
  },
  computed: {
    ...mapState("browser", {
      orderChoices: (state) => state.formChoices.orderBy,
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
        this.$store.dispatch("browser/settingChanged", data);
      },
    },
  },
  methods: {
    toggleOrderReverse: function () {
      const data = { orderReverse: !this.orderReverseSetting };
      this.$store.dispatch("browser/settingChanged", data);
    },
  },
};
</script>

<style scoped lang="scss">
.orderIcon {
  float: right;
}
/* #orderSelect style is handled in browser-filter-toolbar.vue */
</style>

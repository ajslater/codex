<template>
  <v-select
    v-model="sortBy"
    class="toolbarSelect sortBySelect"
    :items="sortChoices"
    dense
    :label="label"
    hide-details="auto"
    ripple
    :menu-props="{
      maxHeight: '90vh',
      overflowY: false,
    }"
    :append-icon="sortIcon"
    @focus="label = 'sort by'"
    @blur="label = ''"
    @click:append="toggleSortReverse"
  >
    <template #item="data">
      <v-list-item v-bind="data.attrs" v-on="data.on">
        <v-list-item-content>
          <v-list-item-title>
            {{ data.item.text }}
            <v-icon v-show="sortBy === data.item.value" class="sortIcon">
              {{ sortIcon }}
            </v-icon>
          </v-list-item-title>
        </v-list-item-content>
      </v-list-item>
    </template>
  </v-select>
</template>

<script>
import { mdiSortReverseVariant, mdiSortVariant } from "@mdi/js";
import { mapState } from "vuex";

export default {
  name: "BrowseSortBySelect",
  data() {
    return {
      mdiSortVariant,
      label: "",
    };
  },
  computed: {
    ...mapState("browser", {
      sortChoices: (state) => state.formChoices.sort,
      sortReverseSetting: (state) => state.settings.sortReverse,
      sortBySetting: (state) => state.settings.sortBy,
      sortIcon: (state) =>
        state.settings.sortReverse ? mdiSortVariant : mdiSortReverseVariant,
    }),
    sortBy: {
      get() {
        return this.sortBySetting;
      },
      set(value) {
        const data = { sortBy: value };
        this.$store.dispatch("browser/settingChanged", data);
      },
    },
  },
  methods: {
    toggleSortReverse: function () {
      const data = { sortReverse: !this.sortReverseSetting };
      this.$store.dispatch("browser/settingChanged", data);
    },
  },
};
</script>

<style scoped lang="scss">
.sortIcon {
  float: right;
}
/* style is also handled in browser-filter-toolbar.vue */
</style>

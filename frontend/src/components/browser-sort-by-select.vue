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
      maxHeight: '80vh',
      overflowY: false,
    }"
    :append-icon="getSortIcon(true)"
    @focus="label = 'sort by'"
    @blur="label = ''"
  >
    <template #item="data">
      <v-list-item v-bind="data.attrs" v-on="data.on">
        <v-list-item-content>
          <v-list-item-title>
            {{ data.item.text }}
            <v-icon v-show="sortBy === data.item.value" class="sortArrow">
              {{ getSortIcon(false) }}
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
      mdiSortReverseVariant,
      mdiSortVariant,
      label: "",
    };
  },
  computed: {
    ...mapState("browser", {
      sortChoices: (state) => state.formChoices.sort,
      sortReverseSetting: (state) => state.settings.sortReverse,
      sortBySetting: (state) => state.settings.sortBy,
    }),
    sortBy: {
      get() {
        return this.sortBySetting;
      },
      set(value) {
        let data = {};
        if (value === this.sortBySetting) {
          data.sortReverse = !this.sortReverseSetting;
        } else {
          data.sortReverse = false;
          data.sortBy = value;
        }
        this.$store.dispatch("browser/settingChanged", data);
      },
    },
  },
  methods: {
    getSortIcon: function (flipIt) {
      // I don't understand why, but the append-icon attribute flips the
      // icon or doesn't update properly, so this is a hack around that.
      let reverse = this.sortReverseSetting;
      if (flipIt) {
        reverse = !reverse;
      }
      if (reverse) {
        return mdiSortReverseVariant;
      }
      return mdiSortVariant;
    },
  },
};
</script>

<style scoped lang="scss">
.sortArrow {
  width: 20px;
  float: right;
  transform: scale(1, -1);
}
.upsideDown {
  transform: rotate(180deg);
}
.sortBySelect {
  width: 144px;
}
@import "~vuetify/src/styles/styles.sass";
@media #{map-get($display-breakpoints, 'sm-and-down')} {
  .sortBySelect {
    width: 114px;
    margin-right: -19px;
  }
}
</style>

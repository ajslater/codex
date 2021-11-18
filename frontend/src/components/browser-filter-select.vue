<template>
  <v-select
    ref="filterSelect"
    v-model="bookmarkFilter"
    :items="bookmarkChoices"
    class="toolbarSelect filterSelect"
    :label="label"
    dense
    hide-details="auto"
    ripple
    :menu-props="{
      maxHeight: '80vh',
      overflowY: false,
      contentClass: filterMenuClass,
    }"
    :prepend-inner-icon="filterInnerIcon"
    @click:prepend-inner="clearFilters"
    @focus="label = 'filter by'"
    @blur="label = ''"
  >
    <template #selection="{ item }">
      {{ item.text }}
      <span v-if="isOtherFiltersSelected" class="filterSuffix"> + </span>
    </template>
    <template #item="data">
      <v-slide-x-transition hide-on-leave>
        <v-list-item-content>
          <v-list-item-title>
            {{ data.item.text }}
          </v-list-item-title>
        </v-list-item-content>
      </v-slide-x-transition>
    </template>
    <template #append-item>
      <v-slide-x-transition hide-on-leave>
        <v-divider v-if="filterMode === 'base'" />
      </v-slide-x-transition>
      <FilterSubMenu
        v-for="filterName of filterNames"
        :key="filterName"
        :name="filterName"
        @sub-menu-click="closeFilterSelect"
      />
    </template>
  </v-select>
</template>

<script>
import { mdiCloseCircle } from "@mdi/js";
import { mapGetters, mapState } from "vuex";

import FilterSubMenu from "@/components/filter-sub-menu";

export default {
  name: "BrowserFilterSelect",
  components: {
    FilterSubMenu,
  },
  data() {
    return {
      label: "",
    };
  },
  computed: {
    ...mapState("browser", {
      bookmarkChoices: (state) => state.formChoices.bookmark,
      filterMode: (state) => state.filterMode,
      filters: (state) => state.settings.filters,
    }),
    ...mapGetters("browser", ["filterNames"]),
    filterMenuClass: function () {
      // Lets me hide bookmark menu items with css when the filterMode
      //   changes.
      let className = "filterMenu";
      if (this.filterMode !== "base") {
        className += "Hidden";
      }
      return className;
    },
    isOtherFiltersSelected: function () {
      for (let filterName of this.filterNames) {
        const filterArray = this.filters[filterName];
        if (filterArray && filterArray.length > 0) {
          return true;
        }
      }
      return false;
    },
    isFiltersClearable: function () {
      if (this.bookmarkFilter !== "ALL") {
        return true;
      }
      return this.isOtherFiltersSelected;
    },
    filterInnerIcon: function () {
      if (this.isFiltersClearable) {
        return mdiCloseCircle;
      }
      return " ";
    },
    bookmarkFilter: {
      get() {
        return this.filters.bookmark;
      },
      set(value) {
        if (value === null || value === undefined) {
          console.warn(`bookmarkFilter was ${value}. Setting to 'ALL'`);
          value = "ALL";
        }
        const data = { filters: { bookmark: value } };
        this.$store.dispatch("browser/settingChanged", data);
      },
    },
  },
  methods: {
    clearFilters: function () {
      this.$store.dispatch("browser/filtersCleared");
    },
    closeFilterSelect: function () {
      // On sub-menu click, close the menu and reset the filter mode.
      this.$refs.filterSelect.blur();
      this.$store.commit("browser/filterModeChanged", "base");
    },
  },
};
</script>

<style scoped lang="scss">
.filterSuffix {
  margin-left: 0.25em;
}
// style is handled in browser-filter-toolbar.vue
</style>

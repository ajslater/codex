<template>
  <v-hover v-slot="{ hover }">
    <v-select
      ref="filterSelect"
      v-model="bookmarkFilter"
      class="toolbarSelect"
      dense
      :items="bookmarkChoices"
      hide-details="auto"
      :label="focused || hover ? LABEL : undefined"
      :aria-label="LABEL"
      :menu-props="{
        maxHeight: '80vh',
        overflowY: false,
        contentClass: filterMenuClass,
      }"
      :prepend-inner-icon="filterInnerIcon"
      ripple
      @click:prepend-inner="clearFilters"
      @focus="focused = true"
      @blur="focused = false"
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
          :name="camelToSnake(filterName)"
          :is-numeric="NUMERIC_FILTERS.includes(filterName)"
          @sub-menu-click="closeFilterSelect"
        />
      </template>
    </v-select>
  </v-hover>
</template>

<script>
import { mdiCloseCircle } from "@mdi/js";
import { mapActions, mapGetters, mapMutations, mapState } from "vuex";

import FilterSubMenu from "@/components/filter-sub-menu.vue";
import { NUMERIC_FILTERS } from "@/store/modules/browser";

export default {
  name: "BrowserFilterSelect",
  components: {
    FilterSubMenu,
  },
  data() {
    return {
      focused: false,
      LABEL: "filter by",
      NUMERIC_FILTERS: NUMERIC_FILTERS,
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
      let clsName = "filterMenu";
      if (this.filterMode !== "base") {
        clsName += "Hidden";
      }
      return clsName;
    },
    isOtherFiltersSelected: function () {
      for (const filterName of this.filterNames) {
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
        let bookmark = value;
        if (bookmark === null || bookmark === undefined) {
          bookmark = "ALL";
          console.warn(`bookmarkFilter was ${value}. Set to 'ALL'`);
        }
        const data = { filters: { bookmark } };
        this.settingChanged(data);
      },
    },
  },
  methods: {
    ...mapActions("browser", ["filtersCleared", "settingChanged"]),
    ...mapMutations("browser", ["setFilterMode"]),
    camelToSnake: function (name) {
      // name is used as the submission value to the API as well async function (arguments) {
      // The widget translates snake_case to Cap Case.
      return name.replace(/[A-Z]/g, (letter) => `_${letter.toLowerCase()}`);
    },
    clearFilters: function () {
      this.filtersCleared();
    },
    closeFilterSelect: function () {
      // On sub-menu click, close the menu and reset the filter mode.
      this.$refs.filterSelect.blur();
      this.setFilterMode("base");
    },
  },
};
</script>

<style scoped lang="scss">
.filterSuffix {
  margin-left: 0.25em;
}
// #filterSelect style is handled in browser-filter-toolbar.vue
</style>

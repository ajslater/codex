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
      @click:prepend-inner="clearFiltersAndChoices"
      @focus="focus"
      @blur="focused = false"
    >
      <template #selection="{ item }">
        {{ item.text }}
        <span v-if="isDynamicFiltersSelected" class="filterSuffix"> + </span>
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
        <BrowserFilterSubMenu
          v-for="filterName of dynamicChoiceNames"
          :key="filterName"
          :name="filterName"
          :is-numeric="NUMERIC_FILTERS.includes(filterName)"
          @sub-menu-click="closeFilterSelect"
        />
      </template>
    </v-select>
  </v-hover>
</template>

<script>
import { mdiCloseCircle } from "@mdi/js";
import { mapActions, mapState } from "pinia";

import BrowserFilterSubMenu from "@/components/browser/filter-sub-menu.vue";
import { NUMERIC_FILTERS, useBrowserStore } from "@/stores/browser";

export default {
  name: "BrowserFilterSelect",
  components: {
    BrowserFilterSubMenu,
  },
  data() {
    return {
      focused: false,
      LABEL: "filter by",
      NUMERIC_FILTERS: NUMERIC_FILTERS,
      dynamicChoiceNames: [],
    };
  },
  computed: {
    ...mapState(useBrowserStore, {
      bookmarkChoices: (state) => state.choices.static.bookmark,
      filterMode: (state) => state.filterMode,
      filters: (state) => state.settings.filters,
      dynamicChoices: (state) => state.choices.dynamic,
      isDynamicFiltersSelected: function (state) {
        for (const [name, array] of Object.entries(state.settings.filters)) {
          if (name !== "bookmark" && array && array.length > 0) {
            return true;
          }
        }
        return false;
      },
      isFiltersClearable: function (state) {
        const defaultBookmarkValues = [
          undefined,
          state.choices.static.bookmark[0].value,
        ];
        return (
          !defaultBookmarkValues.includes(state.settings.filters.bookmark) ||
          this.isDynamicFiltersSelected
        );
      },
      filterMenuClass: function (state) {
        // Lets me hide bookmark menu items with css when the filterMode
        //   changes.
        let clsName = "filterMenu";
        if (state.filterMode !== "base") {
          clsName += "Hidden";
        }
        return clsName;
      },
    }),
    bookmarkFilter: {
      get() {
        return this.filters.bookmark || this.bookmarkChoices[0];
      },
      set(bookmark) {
        const data = { filters: { bookmark } };
        this.setSettings(data);
      },
    },
    //...mapGetters(useBrowserStore, ["dynamicChoiceNames"]),
    filterInnerIcon: function () {
      if (this.isFiltersClearable) {
        return mdiCloseCircle;
      }
      return " ";
    },
  },
  methods: {
    ...mapActions(useBrowserStore, [
      "clearFiltersAndChoices",
      "loadAllFilterChoices",
      "setSettings",
    ]),
    closeFilterSelect: function () {
      // On sub-menu click, close the menu and reset the filter mode.
      this.$refs.filterSelect.blur();
      useBrowserStore().filterMode = "base";
    },
    focus() {
      this.focused = true;
      if (Object.keys(this.dynamicChoices).length === 0) {
        this.loadAllFilterChoices()
          .then((names) => {
            this.dynamicChoiceNames = names;
            return true;
          })
          .catch((error) => console.error(error));
      }
    },
  },
};
</script>

<style scoped lang="scss">
.filterSuffix {
  margin-left: 0.25em;
}
// #filterSelect style is handled in browser/filter-toolbar.vue
</style>

<template>
  <div>
    <v-hover v-slot="{ hover }">
      <v-select
        ref="filterSelect"
        :model-value="bookmarkFilter"
        class="toolbarSelect"
        density="compact"
        :items="bookmarkChoices"
        hide-details="auto"
        :label="focused || hover ? LABEL : undefined"
        :aria-label="LABEL"
        :menu-props="{
          overflowY: false,
          contentClass: filterMenuClass,
        }"
        :prepend-inner-icon="filterInnerIcon"
        @click:prepend-inner="clearFiltersAndChoices"
        @focus="focus"
        @blur="focused = false"
        @update:modelValue="change"
      >
        <template #selection="{ item }">
          {{ item.title }}
          <span v-if="isDynamicFiltersSelected" class="filterSuffix"> + </span>
        </template>
        <template #item="data">
          <v-slide-x-transition hide-on-leave>
            <v-list-item-title>
              {{ data.item.title }}
            </v-list-item-title>
          </v-slide-x-transition>
        </template>
        <template #append-item>
          <v-divider />
          <div v-if="dynamicChoiceNames && dynamicChoiceNames.length > 0">
            <BrowserFilterSubMenu
              v-for="filterName of dynamicChoiceNames"
              :key="filterName"
              :name="filterName"
              @change="changeFilter"
            />
          </div>
          <v-progress-linear
            v-else
            id="availableFiltersProgress"
            rounded
            indeterminate
          />
        </template>
      </v-select>
    </v-hover>
  </div>
</template>

<script>
import { mdiCloseCircle } from "@mdi/js";
import { mapActions, mapState, mapWritableState } from "pinia";

import BrowserFilterSubMenu from "@/components/browser/filter-sub-menu.vue";
import { useBrowserStore } from "@/stores/browser";

export default {
  name: "BrowserFilterSelect",
  components: {
    BrowserFilterSubMenu,
  },
  data() {
    return {
      focused: false,
      LABEL: "filter by",
    };
  },
  computed: {
    ...mapState(useBrowserStore, {
      bookmarkChoices: (state) => state.choices.static.bookmark,
      bookmarkFilter: (state) =>
        state.settings.filters.bookmark || state.choices.static.bookmark[0],
      filters: (state) => state.settings.filters,
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
      dynamicChoiceNames: function (state) {
        const names = [];
        for (const [key, value] of Object.entries(state.choices.dynamic)) {
          if (value) {
            names.push(key);
          }
        }
        return names;
      },
    }),
    ...mapWritableState(useBrowserStore, ["filterMode"]),
    filterInnerIcon: function () {
      return this.isFiltersClearable ? mdiCloseCircle : "";
    },
  },
  methods: {
    ...mapActions(useBrowserStore, [
      "clearFiltersAndChoices",
      "loadAvailableFilterChoices",
      "setSettings",
    ]),
    change(bookmark) {
      const data = { filters: { bookmark } };
      this.changeFilter(data);
    },
    changeFilter(settings) {
      // On sub-menu click, close the menu and reset the filter mode.
      this.$refs.filterSelect.blur();
      this.setSettings(settings);
      this.filterMode = "base";
    },
    focus() {
      this.focused = true;
      if (this.dynamicChoiceNames.length === 0) {
        this.loadAvailableFilterChoices();
      }
    },
  },
};
</script>

<style scoped lang="scss">
.filterSuffix {
  margin-left: 0.25em;
}
#availableFiltersProgress {
  margin: 10px;
  margin-bottom: 2px;
  width: 132px;
}
// #filterSelect style is handled in browser/filter-toolbar.vue
</style>

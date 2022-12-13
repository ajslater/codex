<template>
  <ToolbarSelect
    v-model:menu="menu"
    class="filterBySelect"
    select-label="filter by"
    :clearable="isFiltersClearable"
    :items="bookmarkChoices"
    :menu-props="{
      contentClass: filterMenuClass,
    }"
    :model-value="bookmarkFilter"
    :style="style"
    @click:clear="onClear"
    @update:modelValue="onUpdateModelValue"
    @update:menu="onMenu"
  >
    <template #selection="{ item }">
      {{ item.title }}
      <v-icon v-if="isDynamicFiltersSelected" class="filterSuffix">
        {{ mdiFilterMultipleOutline }}
      </v-icon>
    </template>
    <template #append-item>
      <div v-if="dynamicChoiceNames && dynamicChoiceNames.length > 0">
        <v-divider />
        <BrowserFilterSubMenu
          v-for="filterName of dynamicChoiceNames"
          :key="filterName"
          :name="filterName"
          @selected="onSubMenuSelected"
        />
      </div>
      <v-progress-linear
        v-else
        id="availableFiltersProgress"
        rounded
        indeterminate
      />
    </template>
  </ToolbarSelect>
</template>

<script>
import { mdiCloseCircle, mdiFilterMultipleOutline } from "@mdi/js";
import { mapActions, mapGetters, mapState, mapWritableState } from "pinia";

import BrowserFilterSubMenu from "@/components/browser/filter-sub-menu.vue";
import ToolbarSelect from "@/components/browser/toolbar-select.vue";
import { useBrowserStore } from "@/stores/browser";

export default {
  name: "BrowserFilterBySelect",
  components: {
    BrowserFilterSubMenu,
    ToolbarSelect,
  },
  extends: ToolbarSelect,
  data() {
    return {
      mdiFilterMultipleOutline,
      menu: false,
    };
  },
  computed: {
    ...mapGetters(useBrowserStore, [
      // eslint-disable-next-line no-secrets/no-secrets
      "filterByChoicesMaxLen",
      "isDefaultBookmarkValueSelected",
    ]),
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
      isFiltersClearable: function () {
        return (
          !this.isDefaultBookmarkValueSelected || this.isDynamicFiltersSelected
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
      style() {
        const len = this.filterByChoicesMaxLen + 2 + "em";
        return `width: ${len}; min-width: ${len}; max-width: ${len}`;
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
    onUpdateModelValue(bookmark) {
      const data = { filters: { bookmark } };
      this.onSubMenuSelected(data);
    },
    onSubMenuSelected(settings) {
      // On sub-menu click, close the menu and reset the filter mode.
      this.menu = false;
      this.setSettings(settings);
      this.filterMode = "base";
    },
    onClear() {
      this.menu = false;
      this.clearFiltersAndChoices();
    },
    onMenu(to) {
      if (to && this.dynamicChoiceNames.length === 0) {
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
/* #filterSelect style is handled in browser/filter-toolbar.vue */
</style>

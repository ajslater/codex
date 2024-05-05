<template>
  <ToolbarSelect
    v-model:menu="menu"
    class="filterBySelect"
    select-label="filter by"
    :items="bookmarkChoices"
    :menu-props="{
      contentClass: filterMenuClass,
      maxHeight: undefined,
    }"
    :model-value="bookmarkFilter"
    :max-select-len="filterByChoicesMaxLen - 1"
    @update:model-value="onUpdateModelValue"
    @update:menu="onMenu"
  >
    <!--
    :clearable="isFiltersClearable"
    @click:clear="onClear"
    -->
    <template #selection="{ item }">
      <span class="codexSelection"> {{ item.title }} </span>
      <v-icon
        v-if="isDynamicFiltersSelected"
        class="filterSuffix"
        size="x-small"
      >
        {{ mdiFilterMultipleOutline }}
      </v-icon>
    </template>
    <template #prepend-item>
      <v-list-item
        v-if="isFiltersClearable"
        density="compact"
        variant="plain"
        class="clearFilter"
        @click="onClear"
      >
        Clear Filter<v-icon class="clearIcon">{{
          mdiCloseCircleOutline
        }}</v-icon>
      </v-list-item>
    </template>
    <template #append-item>
      <v-divider />
      <v-list-item
        v-if="dynamicChoiceNames === undefined"
        density="compact"
        variant="plain"
      >
        <v-progress-linear indeterminate rounded />
      </v-list-item>
      <BrowserFilterSubMenu
        v-for="filterName of dynamicChoiceNames"
        v-else-if="dynamicChoiceNames.length > 0"
        :key="filterName"
        :name="filterName"
        @selected="onSubMenuSelected"
      />
      <v-list-item v-else class="noChoices" density="compact" variant="plain">
        No filters available
      </v-list-item>
    </template>
  </ToolbarSelect>
</template>

<script>
import { mdiCloseCircleOutline, mdiFilterMultipleOutline } from "@mdi/js";
import { mapActions, mapGetters, mapState, mapWritableState } from "pinia";

import ToolbarSelect from "@/components/browser/toolbars/toolbar-select.vue";
import BrowserFilterSubMenu from "@/components/browser/toolbars/top/filter-sub-menu.vue";
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
      mdiCloseCircleOutline,
      mdiFilterMultipleOutline,
      menu: false,
    };
  },
  computed: {
    ...mapGetters(useBrowserStore, [
      // eslint-disable-next-line no-secrets/no-secrets
      "filterByChoicesMaxLen",
      "isDynamicFiltersSelected",
      "isFiltersClearable",
    ]),
    ...mapState(useBrowserStore, {
      bookmarkChoices: (state) => state.choices.static.bookmark,
      bookmarkFilter: (state) =>
        state.settings.filters.bookmark || state.choices.static.bookmark[0],
      filters: (state) => state.settings.filters,
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
        if (state.choices.dynamic === undefined) {
          return;
        }
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
  },
  methods: {
    ...mapActions(useBrowserStore, [
      "clearFilters",
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
      this.clearFilters();
    },
    onMenu(to) {
      if (to && this.dynamicChoiceNames === undefined) {
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
.noChoices {
  color: rgb(var(--v-theme-textDisabled));
}
.clearFilter {
  color: black;
  background-color: rgb(var(--v-theme-primary))
}
.clearIcon {
  float: right;
}
</style>

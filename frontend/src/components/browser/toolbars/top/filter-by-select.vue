<template>
  <ToolbarSelect
    v-model:menu="menu"
    class="filterBySelect"
    :class="{ filterBySelectXSmall: padRight }"
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
        title="Clear All Filters"
        :append-icon="mdiCloseCircleOutline"
        @click="onClear"
      />
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
      <v-list-item
        v-else
        class="noChoices"
        density="compact"
        variant="plain"
        title="No filters available"
      />
    </template>
  </ToolbarSelect>
</template>

<script>
import { mdiCloseCircleOutline, mdiFilterMultipleOutline } from "@mdi/js";
import { mapActions, mapState, mapWritableState } from "pinia";

import BrowserFilterSubMenu from "@/components/browser/toolbars/top/filter-sub-menu.vue";
import ToolbarSelect from "@/components/toolbar-select.vue";
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
    ...mapState(useBrowserStore, [
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
        /*
         * Let me hide bookmark menu items with css when the filterMode
         *   changes.
         */
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
    padRight() {
      return this.$vuetify.display.xs && !this.bookmarkFilter;
    },
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
      return this.clearFilters()
        .then(() => {
          return this.loadAvailableFilterChoices();
        })
        .catch(() => {
          console.error("clear filters");
        });
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
.filterBySelectXSmall {
  padding-right: 0.4em;
}

.filterSuffix {
  margin-left: 0.25em;
}

.noChoices {
  color: rgb(var(--v-theme-textDisabled));
}

.clearFilter {
  color: black;
  background-color: rgb(var(--v-theme-primary));
}
</style>

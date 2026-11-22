<template>
  <ToolbarSelect
    v-model:menu="menu"
    class="filterBySelect"
    :class="{ filterBySelectXSmall: padRight }"
    select-label="filter by"
    :items="bookmarkChoices"
    :menu-props="{
      contentClass: filterMenuClass,
      contentProps: { onKeydownCapture: onMenuKeydownCapture },
      maxHeight: undefined,
      closeOnContentClick: false,
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
      <!--
        Rows of the filter list itself. While a sub-menu is open it shows
        only its own rows, so a first tick there adds no row above it.
      -->
      <v-list-item
        v-if="isFiltersClearable && isBaseMode"
        density="compact"
        variant="plain"
        class="clearFilter"
        title="Clear All Filters"
        :append-icon="mdiCloseCircleOutline"
        @click="onClear"
      />
    </template>
    <template #append-item>
      <v-divider v-if="isBaseMode" />
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
import { mapActions, mapState } from "pinia";

import BrowserFilterSubMenu from "@/components/browser/toolbars/top/filter-sub-menu.vue";
import ToolbarSelect from "@/components/toolbar-select.vue";
import { useAuthStore } from "@/stores/auth";
import { useBrowserStore } from "@/stores/browser";

const ARROW_STEPS = Object.freeze({ ArrowDown: 1, ArrowUp: -1 });
/*
 * Vuetify focuses list rows programmatically with ``tabindex="-2"`` and
 * parks the list itself at ``-1``, so excluding only ``-1`` selects exactly
 * the rows its own focus walk would visit.
 */
const FOCUSABLE_ROW = '[tabindex]:not([tabindex="-1"]):not([disabled])';

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
    ...mapState(useAuthStore, {
      siteBookmarkDefault: (state) => state.defaults?.browser?.bookmark ?? "",
    }),
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
      isBaseMode: (state) => state.filterMode === "base",
      filterMenuClass: function (state) {
        // Hides the bookmark rows while a sub-menu is open: global.scss.
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
        // Add selected filters to choices if they aren't there already.
        if (this.filters && Object.keys(this.filters).length) {
          for (const [filterKey, filterValue] of Object.entries(this.filters)) {
            if (
              filterKey !== "bookmark" &&
              filterValue?.length &&
              !names.includes(filterKey)
            ) {
              names.push(filterKey);
            }
          }
        }
        /*
         * ``ageRatingTagged`` is folded into the ``ageRatingMetron``
         * sub-menu's "As tagged" expansion panel: the top-level row
         * is always ``ageRatingMetron``. Ensure ``ageRatingMetron``
         * is present whenever *either* key has choices/selections so
         * the user can still reach the As-tagged panel even if no
         * normalized metron values are available for the current
         * group. Then drop the standalone ``ageRatingTagged`` entry.
         */
        const taggedIdx = names.indexOf("ageRatingTagged");
        if (taggedIdx >= 0) {
          names.splice(taggedIdx, 1);
          if (!names.includes("ageRatingMetron")) {
            names.push("ageRatingMetron");
          }
        }
        names.sort();
        return names;
      },
    }),
    padRight() {
      return this.$vuetify.display.xs && !this.bookmarkFilter;
    },
  },
  watch: {
    menu(open) {
      /*
       * However the menu opens or closes. The store keeps an open menu's
       * choices across page loads; closing returns it to the filter list
       * and drops choices gone stale.
       */
      this.setFilterMenuOpen(open);
    },
  },
  beforeUnmount() {
    // Leaving with the menu open, as to the reader, closes it for the store.
    if (this.menu) {
      this.setFilterMenuOpen(false);
    }
  },
  methods: {
    ...mapActions(useBrowserStore, [
      "clearFilters",
      "loadAvailableFilterChoices",
      "setFilterMenuOpen",
      "setSettings",
      "tickFilters",
    ]),
    onUpdateModelValue(bookmark) {
      // A bookmark pick applies and closes the menu; closing resets it.
      this.menu = false;
      this.setSettings({ filters: { bookmark } });
    },
    onSubMenuSelected({ filters }) {
      // A tick: the menu stays open on its sub-menu, the page reloads behind.
      this.tickFilters(filters);
    },
    async onClear() {
      try {
        await this.clearFilters();
        /*
         * Belt-and-suspenders. ``clearFilters`` patches state with
         * whatever ``API.resetSettings`` returns, but the server's
         * reset has been observed to leave some keys populated —
         * sometimes the Age Rating pair, sometimes the bookmark.
         * As long as ``isFiltersClearable`` returns true, the
         * "Clear All Filters" row stays rendered (its ``v-if``),
         * making it look like the click did nothing. Force a fully
         * cleared state here: zero every non-bookmark filter, set
         * bookmark to the site default (what a reset restores), and
         * explicitly seed the Age Rating pair from the dual-panel UI
         * in case the current group's filter state doesn't expose them.
         */
        if (this.isFiltersClearable) {
          const emptyDynamic = Object.fromEntries(
            Object.keys(this.filters || {})
              .filter((key) => key !== "bookmark")
              .map((key) => [key, []]),
          );
          const clearedFilters = {
            bookmark: this.siteBookmarkDefault,
            ...emptyDynamic,
            ageRatingMetron: [],
            ageRatingTagged: [],
          };
          await this.setSettings({ filters: clearedFilters });
        }
        await this.loadAvailableFilterChoices();
      } catch {
        console.error("clear filters");
      }
    },
    onMenu(to) {
      if (to && this.dynamicChoiceNames === undefined) {
        this.loadAvailableFilterChoices();
      }
    },
    /*
     * Vuetify 4.2 moved select keyboard navigation into ``useScrolling``,
     * which wraps from the last bookmark row straight back to the first and
     * calls ``stopImmediatePropagation()``. That preempts VList's own focus
     * walk, which is what used to carry the user into the rows this menu
     * adds through the prepend/append slots ("Clear All Filters" and the
     * filter sub-menus), leaving them mouse-only.
     * A capture listener on the overlay content runs before the list's, so
     * stepping off either end of the bookmark rows lands on the adjacent
     * slot row instead of wrapping. Everywhere else the event is left alone
     * and Vuetify still owns the navigation.
     */
    onMenuKeydownCapture(event) {
      const step = ARROW_STEPS[event.key];
      const content = event.currentTarget;
      const row = document.activeElement?.closest?.("[aria-posinset]");
      if (!step || !row || !content.contains(row)) {
        return;
      }
      // Only the true ends of the bookmark list wrap; mid-list rows are fine.
      const end = step > 0 ? Number(row.getAttribute("aria-setsize")) : 1;
      if (Number(row.getAttribute("aria-posinset")) !== end) {
        return;
      }
      const rows = [...content.querySelectorAll(FOCUSABLE_ROW)];
      const target = rows[rows.indexOf(row) + step];
      if (!target || target.hasAttribute("aria-posinset")) {
        return;
      }
      event.preventDefault();
      event.stopPropagation();
      target.focus();
    },
  },
};
</script>

<style scoped lang="scss">
/* Layered: these rules beat Vuetify's component CSS by position,
 * and lose to a `color`/utility prop, which is the intended order. */
@layer codex-components {
  .filterBySelectXSmall {
    padding-right: 0.4em;
  }

  .filterSuffix {
    margin-left: 0.25em;
  }

  .noChoices {
    color: rgb(var(--v-theme-text-disabled));
  }

  .clearFilter {
    color: rgb(var(--v-theme-on-primary));
    background-color: rgb(var(--v-theme-primary));
  }
}
</style>

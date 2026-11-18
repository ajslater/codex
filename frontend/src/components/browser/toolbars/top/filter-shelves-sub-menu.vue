<template>
  <div>
    <v-slide-x-transition hide-on-leave>
      <v-list-item
        v-if="filterMode === 'base'"
        class="shelvesFilter"
        density="compact"
        variant="plain"
        title="Shelves"
        :active="isActive"
        :append-icon="filterMenuIcon"
        @click="filterMode = FILTER_MODE"
      />
    </v-slide-x-transition>
    <v-slide-x-reverse-transition hide-on-leave>
      <div v-if="filterMode === FILTER_MODE">
        <header class="filterHeader">
          <v-list-item
            class="filterHeaderTitle"
            :prepend-icon="mdiChevronLeft"
            title="shelves"
            @click="filterMode = 'base'"
          />
          <v-list-item
            v-if="isActive"
            density="compact"
            class="clearFilter clearShelvesFilter"
            title="Clear Filter"
            :append-icon="mdiCloseCircleOutline"
            @click="setShelves([])"
          />
        </header>
        <v-list class="shelvesFilterList overflow-y-auto" density="compact">
          <v-list-item
            v-for="shelf of shelfRows"
            :key="shelf.pk"
            class="shelvesFilterRow"
            density="compact"
            variant="plain"
            role="menuitemcheckbox"
            :aria-checked="String(shelf.selected)"
            :title="shelf.name"
            @click="onToggle(shelf)"
          >
            <template #prepend>
              <v-checkbox-btn
                density="compact"
                :model-value="shelf.selected"
                tabindex="-1"
                readonly
              />
            </template>
          </v-list-item>
        </v-list>
      </div>
    </v-slide-x-reverse-transition>
  </div>
</template>

<script>
import {
  mdiChevronLeft,
  mdiChevronRight,
  mdiChevronRightCircle,
  mdiCloseCircleOutline,
} from "@mdi/js";
import { mapActions, mapState, mapWritableState } from "pinia";

import { useBrowserStore } from "@/stores/browser";
import { useShelvesStore } from "@/stores/shelves";

/*
 * The "Shelves" entry of the filter menu. A sibling of
 * ``filter-sub-menu.vue`` rather than a use of it: that one loads its
 * choices from the browser choices endpoints and applies a single pick
 * then closes, while this lists the user's shelves from the shelves
 * store as checkboxes, several of which can be ticked while the menu
 * stays open. A row on any ticked shelf matches.
 */
const FILTER_MODE = "shelves";

export default {
  name: "BrowserFilterShelvesSubMenu",
  data() {
    return {
      FILTER_MODE,
      mdiChevronLeft,
      mdiCloseCircleOutline,
    };
  },
  computed: {
    ...mapState(useBrowserStore, {
      filter: (state) => state.settings.filters.shelves || [],
    }),
    ...mapState(useShelvesStore, ["shelves"]),
    ...mapWritableState(useBrowserStore, ["filterMode"]),
    shelfRows() {
      // The store keeps shelves ordered by name.
      return this.shelves.map(({ pk, name }) => ({
        pk,
        name,
        selected: this.filter.includes(pk),
      }));
    },
    isActive() {
      return this.filter.length > 0;
    },
    filterMenuIcon() {
      return this.isActive ? mdiChevronRightCircle : mdiChevronRight;
    },
  },
  methods: {
    ...mapActions(useBrowserStore, [
      "loadAvailableFilterChoices",
      "setSettings",
    ]),
    async setShelves(shelves) {
      await this.setSettings({ filters: { shelves } });
      // The page reload clears the other filters' choices; fetch them
      // again for the menu that is still open.
      await this.loadAvailableFilterChoices();
    },
    onToggle(shelf) {
      const shelves = shelf.selected
        ? this.filter.filter((pk) => pk !== shelf.pk)
        : [...this.filter, shelf.pk];
      this.setShelves(shelves);
      /*
       * Saving settings drops the menu back to its base mode. Stay on
       * the shelf list so several shelves can be ticked in one visit;
       * both writes land in the same tick, so nothing re-renders.
       */
      this.filterMode = FILTER_MODE;
    },
  },
};
</script>

<style scoped lang="scss">
/* Layered: these rules beat Vuetify's component CSS by position,
 * and lose to a `color`/utility prop, which is the intended order. */
@layer codex-components {
  .filterHeaderTitle :deep(.v-list-item__prepend > .v-list-item__spacer) {
    display: none;
  }

  .filterHeaderTitle :deep(.v-list-item-title) {
    font-variant: small-caps;
    color: rgb(var(--v-theme-text-disabled));
    font-weight: bold;
    font-size: 1.6rem !important;
  }

  .clearFilter {
    color: rgb(var(--v-theme-on-primary));
    background-color: rgb(var(--v-theme-primary));
    opacity: 0.7;
  }

  .clearFilter:hover {
    opacity: 1;
  }

  .shelvesFilterList {
    max-height: 80vh;
    /* has to be less than the menu height */
  }

  .shelvesFilterRow :deep(.v-list-item__prepend > .v-list-item__spacer) {
    width: 8px;
  }
}
</style>

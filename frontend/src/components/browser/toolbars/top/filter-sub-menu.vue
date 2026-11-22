<template>
  <div>
    <v-slide-x-transition hide-on-leave>
      <v-list-item
        v-if="filterMode === 'base'"
        class="filterSubMenuRow"
        :class="{ filterRowTicked: isActive }"
        density="compact"
        variant="plain"
        :title="title"
        :active="isActive"
        @click="setUIFilterMode(name)"
      >
        <template #append>
          <span v-if="tickedCount" class="filterTickedCount">{{
            tickedCount
          }}</span>
          <v-icon :icon="filterMenuIcon" />
        </template>
      </v-list-item>
    </v-slide-x-transition>
    <v-slide-x-reverse-transition hide-on-leave>
      <div v-if="filterMode === name" @keydown="onSubMenuKeydown">
        <header class="filterHeader">
          <v-list-item
            class="filterHeaderTitle"
            :prepend-icon="mdiChevronLeft"
            :title="lowerTitle"
            @click="setUIFilterMode('base')"
          />
          <!--
            Kept in place, unseen, with nothing ticked: the first tick
            would otherwise push every row down under the pointer.
          -->
          <v-list-item
            density="compact"
            class="clearFilter"
            :class="{ clearFilterIdle: !isClearable }"
            title="Clear Filter"
            :append-icon="mdiCloseCircleOutline"
            :disabled="!isClearable"
            :aria-hidden="isClearable ? undefined : 'true'"
            @click="onClear"
          />
          <v-text-field
            v-if="hasAnyChoices"
            v-model="search"
            placeholder="Filter"
            full-width
            density="compact"
            filled
            rounded
            hide-details="auto"
            @keydown="onSearchKeydown"
          />
          <v-progress-linear
            v-else
            class="filterValuesProgress"
            rounded
            indeterminate
          />
          <!--
            Tag-like filters only, and always shown there, so the list
            does not move when a value is ticked.
          -->
          <v-switch
            v-if="isTagLike"
            class="matchAllSwitch"
            color="primary"
            density="compact"
            hide-details
            label="Match all ticked"
            :model-value="isMatchAll"
            @update:model-value="onMatchAll"
          />
          <div v-if="isMatchAll" class="matchAllHint">
            {{ matchAllHint }}
          </div>
        </header>
        <!--
          Age Rating: dual-tab UI. The "Standardized" tab (metron
          values) is selected by default; "As tagged" holds every
          raw tagged value, each preceded by its standardized
          equivalent in a dim left column. When there are no tagged
          values the tab bar is hidden and only the Standardized
          list renders. A tab shows a primary-colored checkbox
          icon when its filter has any selections. The shared
          search box at the top filters both tabs' items at once;
          if matches land only in the other tab, the view switches
          to it.
        -->
        <template v-if="isAgeRating">
          <v-tabs
            v-if="hasTaggedChoices"
            v-model="activeTab"
            grow
            density="compact"
          >
            <v-tab
              v-for="panel of ageRatingPanels"
              :key="panel.key"
              :value="panel.key"
            >
              <v-icon
                v-if="panel.hasSelections"
                class="ageRatingTabSelectedIcon"
                :icon="mdiCheckboxMarked"
                size="small"
                start
              />
              {{ panel.label }}
            </v-tab>
          </v-tabs>
          <v-window v-model="activeTab">
            <v-window-item
              v-for="panel of ageRatingPanels"
              :key="panel.key"
              :value="panel.key"
            >
              <BrowserFilterChoiceList
                :name="panel.key"
                :choices="panel.choices"
                :filter="panel.filter"
                :search="search"
                @selected="(v) => onAgeRatingSelected(panel.key, v)"
              />
            </v-window-item>
          </v-window>
        </template>
        <BrowserFilterChoiceList
          v-else-if="hasAnyChoices"
          :name="name"
          :choices="choices"
          :filter="filter"
          :search="search"
          :match-all="isMatchAll"
          @selected="onSelected"
        />
      </div>
    </v-slide-x-reverse-transition>
  </div>
</template>

<script>
import {
  mdiCheckboxMarked,
  mdiChevronLeft,
  mdiChevronRight,
  mdiChevronRightCircle,
  mdiCloseCircleOutline,
} from "@mdi/js";
import { mapActions, mapState, mapWritableState } from "pinia";
import { capitalCase } from "text-case";

import BROWSER_CHOICES, {
  VUETIFY_NULL_CODE,
} from "@/choices/browser-choices.json";
import { NULL_PKS, toVuetifyItems } from "@/vuetify-items";
import BrowserFilterChoiceList from "@/components/browser/toolbars/top/filter-choice-list.vue";
import { MATCH_ALL_FILTER, useBrowserStore } from "@/stores/browser";

const FILTER_TITLE_OVERRIDES = {
  ageRatingMetron: "Age Rating",
  // "Reprints" reads as reprint editions; these are alternate and
  // localized series names.
  reprints: "Reprints",
};
// Tab values are the filter keys; "Standardized" is the default tab.
const AGE_RATING_DEFAULT_TAB = "ageRatingMetron";
/*
 * The filters a comic holds several values of, where "Match all ticked"
 * means something. Defined once on the server; see make build-choices.
 */
const TAG_LIKE_FILTERS = Object.freeze(
  new Set(BROWSER_CHOICES.MATCH_ALL_FILTERS),
);
// A tick in one Age Rating tab narrows the other tab's choices.
const OTHER_AGE_RATING_TAB = Object.freeze({
  ageRatingMetron: "ageRatingTagged",
  ageRatingTagged: "ageRatingMetron",
});

export default {
  name: "BrowserFilterSubMenu",
  components: { BrowserFilterChoiceList },
  props: {
    name: {
      type: String,
      required: true,
    },
  },
  emits: ["selected"],
  data() {
    return {
      mdiCheckboxMarked,
      mdiChevronLeft,
      mdiCloseCircleOutline,
      search: "",
      activeTab: AGE_RATING_DEFAULT_TAB,
      // The list to refetch once the page reloads after a tick.
      refreshAfterLoad: undefined,
      matchAllHint: "Dimmed rows don't occur with every ticked value.",
    };
  },
  computed: {
    ...mapState(useBrowserStore, {
      choices(state) {
        return state.choices.dynamic[this.name];
      },
      filter(state) {
        return state.settings.filters[this.name];
      },
      metronChoices: (state) => state.choices.dynamic.ageRatingMetron,
      taggedChoices: (state) => state.choices.dynamic.ageRatingTagged,
      metronFilter: (state) => state.settings.filters.ageRatingMetron,
      taggedFilter: (state) => state.settings.filters.ageRatingTagged,
      choicesStale: (state) => state.choicesStale,
      page: (state) => state.page,
      matchAllFilters: (state) =>
        state.settings.filters[MATCH_ALL_FILTER] || [],
    }),
    ...mapWritableState(useBrowserStore, ["filterMode"]),
    isAgeRating() {
      return this.name === "ageRatingMetron";
    },
    metronHasSelections() {
      return this.metronFilter?.length > 0;
    },
    taggedHasSelections() {
      return this.taggedFilter?.length > 0;
    },
    /*
     * The As-tagged tab exposes every raw tagged age-rating string.
     * Hide the tab only when the library has no tagged values at all
     * (just the ``None`` sentinel, which the Standardized tab already
     * surfaces) — then the second tab would duplicate the first.
     */
    hasTaggedChoices() {
      if (!Array.isArray(this.taggedChoices)) return false;
      return this.taggedChoices.some((c) => !NULL_PKS.has(c?.pk));
    },
    ageRatingPanels() {
      const panels = [
        {
          key: "ageRatingMetron",
          label: "Standardized",
          choices: this.metronChoices,
          filter: this.metronFilter,
          hasSelections: this.metronHasSelections,
        },
      ];
      if (this.hasTaggedChoices) {
        panels.push({
          key: "ageRatingTagged",
          label: "As tagged",
          choices: this.taggedChoices,
          filter: this.taggedFilter,
          hasSelections: this.taggedHasSelections,
        });
      }
      return panels;
    },
    title() {
      return FILTER_TITLE_OVERRIDES[this.name] || capitalCase(this.name);
    },
    lowerTitle() {
      return this.title.toLowerCase();
    },
    isActive() {
      if (this.isAgeRating) {
        return this.metronHasSelections || this.taggedHasSelections;
      }
      return this.filter && this.filter.length > 0;
    },
    filterMenuIcon() {
      return this.isActive ? mdiChevronRightCircle : mdiChevronRight;
    },
    tickedCount() {
      if (this.isAgeRating) {
        return (
          (this.metronFilter?.length ?? 0) + (this.taggedFilter?.length ?? 0)
        );
      }
      return this.filter?.length ?? 0;
    },
    isOpen() {
      return this.filterMode === this.name;
    },
    isTagLike() {
      return TAG_LIKE_FILTERS.has(this.name);
    },
    isMatchAll() {
      return this.isTagLike && this.matchAllFilters.includes(this.name);
    },
    isClearable() {
      if (this.isAgeRating) {
        return this.metronHasSelections || this.taggedHasSelections;
      }
      return this.filter?.length;
    },
    hasAnyChoices() {
      if (this.isAgeRating) {
        return (
          typeof this.metronChoices === "object" ||
          typeof this.taggedChoices === "object"
        );
      }
      return typeof this.choices === "object";
    },
  },
  watch: {
    search(val) {
      if (!this.isAgeRating || !this.hasTaggedChoices || !val) {
        return;
      }
      /*
       * Switch tabs based on where the search has matches: if matches
       * are exclusive to the other tab, jump to it so the user isn't
       * staring at an empty list. With matches in both (or neither)
       * tab, or when the search is cleared, stay on the current tab.
       */
      const metronMatches = this._countMatches(this.metronChoices, val);
      const taggedMatches = this._countMatches(this.taggedChoices, val);
      if (taggedMatches > 0 && metronMatches === 0) {
        this.activeTab = "ageRatingTagged";
      } else if (metronMatches > 0 && taggedMatches === 0) {
        this.activeTab = AGE_RATING_DEFAULT_TAB;
      }
    },
    hasTaggedChoices(val) {
      // The As-tagged tab can vanish after a clear or re-filter;
      // don't leave the window pointed at a tab that no longer exists.
      if (!val) {
        this.activeTab = AGE_RATING_DEFAULT_TAB;
      }
    },
    page() {
      /*
       * The page reloaded after a tick. Under Any a filter's own value
       * leaves its own list alone, so only the other Age Rating tab can
       * have changed; under All the open list narrows to what still
       * occurs with the ticked values. Refetch it in place.
       */
      const key = this.refreshAfterLoad;
      if (!key || !this.isOpen) {
        return;
      }
      this.refreshAfterLoad = undefined;
      this.loadFilterChoices(key);
    },
    choices(value) {
      this._loadIfEmptied(this.name, value);
    },
    taggedChoices(value) {
      if (this.isAgeRating) {
        this._loadIfEmptied("ageRatingTagged", value);
      }
    },
  },
  methods: {
    ...mapActions(useBrowserStore, [
      "clearOneFilter",
      "loadAvailableFilterChoices",
      "loadFilterChoices",
      "setSettings",
    ]),
    setUIFilterMode(mode) {
      this.filterMode = mode;
      this.search = "";
      this.activeTab = AGE_RATING_DEFAULT_TAB;
      this.refreshAfterLoad = undefined;
      if (mode === "base") {
        /*
         * Back at the filter list: refetch which filters are on offer
         * once, here, after ticks made them stale. It is the slow request,
         * so it is never sent per tick. The rows stay until it answers.
         */
        if (this.choicesStale) {
          this.loadAvailableFilterChoices();
        }
        return;
      }
      if (typeof this.choices !== "object" || this.choicesStale) {
        this.loadFilterChoices(mode);
      }
      /*
       * Entering Age Rating: also kick off the tagged-choices fetch
       * so the As-tagged panel can render without its own loading
       * state when the user expands it.
       */
      if (
        this.isAgeRating &&
        (typeof this.taggedChoices !== "object" || this.choicesStale)
      ) {
        this.loadFilterChoices("ageRatingTagged");
      }
    },
    _loadIfEmptied(fieldName, value) {
      // Choices replaced while this sub-menu is open load again, in place.
      if (this.isOpen && typeof value !== "object") {
        this.loadFilterChoices(fieldName);
      }
    },
    onSubMenuKeydown(event) {
      /*
       * Vuetify's select picks a bookmark for any printable key pressed
       * in its list, and a bookmark pick closes the menu. Keep those keys
       * in the sub-menu; Escape and the navigation keys go through.
       */
      const isPrintable =
        event.key?.length === 1 &&
        !event.ctrlKey &&
        !event.metaKey &&
        !event.altKey;
      if (isPrintable) {
        event.stopPropagation();
      }
    },
    onSearchKeydown(event) {
      /*
       * Prevent typed characters from bubbling up to the parent
       * v-select / v-list. Without this, Vuetify's built-in
       * type-to-select keyboard handler intercepts the second or
       * third printable keystroke and closes the whole filter menu.
       * Escape is allowed through so the user can still dismiss
       * the menu with the keyboard.
       */
      if (event.key !== "Escape") {
        event.stopPropagation();
      }
    },
    onSelected(value) {
      if (this.isMatchAll) {
        this.refreshAfterLoad = this.name;
      }
      this.$emit("selected", { filters: { [this.name]: value } });
    },
    onMatchAll(on) {
      const others = this.matchAllFilters.filter((name) => name !== this.name);
      const filters = {
        [MATCH_ALL_FILTER]: on ? [...others, this.name] : others,
      };
      if (on && this.filter?.includes(VUETIFY_NULL_CODE)) {
        // None cannot combine with All.
        filters[this.name] = this.filter.filter(
          (value) => value !== VUETIFY_NULL_CODE,
        );
      }
      this.refreshAfterLoad = this.name;
      this.$emit("selected", { filters });
    },
    onAgeRatingSelected(key, value) {
      this.refreshAfterLoad = OTHER_AGE_RATING_TAB[key];
      this.$emit("selected", { filters: { [key]: value } });
    },
    async _loadSubAvailableFilterChoices() {
      await this.loadAvailableFilterChoices();
      if (this.isAgeRating) {
        await Promise.all([
          this.loadFilterChoices("ageRatingMetron"),
          this.loadFilterChoices("ageRatingTagged"),
        ]);
      } else {
        await this.loadFilterChoices(this.name);
      }
    },
    async onClear() {
      // Back to the filter list; a settings change no longer does it.
      this.filterMode = "base";
      if (this.isAgeRating) {
        /*
         * Single setSettings call clears both keys atomically;
         * _addSettings shallow-merges so other filter keys are
         * preserved.
         */
        await this.setSettings({
          filters: {
            ageRatingMetron: [],
            ageRatingTagged: [],
          },
        });
      } else {
        await this.clearOneFilter(this.name);
      }
      await this._loadSubAvailableFilterChoices();
    },
    _countMatches(choices, search) {
      if (typeof choices !== "object" || !Array.isArray(choices)) {
        return 0;
      }
      /*
       * Reuse the same filter pipeline that BrowserFilterChoiceList
       * uses, so search-match counts always match what the user would
       * see if the panel were expanded.
       *
       * Perf note: only the ``.length`` is used, but ``toVuetifyItems``
       * still allocates the full mapped array (and the "None" prepend).
       * If filter typing ever feels laggy on large choice lists, expose
       * a count-only helper from ``vuetify-items.js`` that walks the
       * source and increments a counter without allocating.
       */
      return toVuetifyItems({
        items: choices,
        filter: search,
        sortBy: "",
      }).length;
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

  .filterValuesProgress {
    margin: 10px;
    width: 88%;
  }

  .clearFilter {
    color: rgb(var(--v-theme-on-primary));
    background-color: rgb(var(--v-theme-primary));
    opacity: 0.7;
  }

  .clearFilter:hover {
    opacity: 1;
  }

  .clearFilterIdle {
    visibility: hidden;
  }

  // A plain row sits at 0.62 opacity unless hovered; one with ticks doesn't.
  .filterRowTicked {
    opacity: 1;
  }

  .matchAllSwitch {
    padding-left: 16px;
  }

  .matchAllHint {
    padding: 0 16px 4px;
    color: rgb(var(--v-theme-text-disabled));
    font-size: smaller;
  }

  .filterTickedCount {
    margin-right: 4px;
    color: rgb(var(--v-theme-primary));
    font-size: smaller;
  }

  /*
   * The selections indicator must stay primary-colored even on the
   * inactive (dimmed) tab, where Vuetify lowers the tab content's
   * opacity.
   */
  .ageRatingTabSelectedIcon {
    color: rgb(var(--v-theme-primary));
    opacity: 1;
  }
}
</style>

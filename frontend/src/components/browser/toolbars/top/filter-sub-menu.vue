<template>
  <div>
    <v-slide-x-transition hide-on-leave>
      <v-list-item
        v-if="filterMode === 'base'"
        density="compact"
        variant="plain"
        :title="title"
        :active="isActive"
        :append-icon="filterMenuIcon"
        @click="setUIFilterMode(name)"
      />
    </v-slide-x-transition>
    <v-slide-x-reverse-transition hide-on-leave>
      <div v-if="filterMode === name">
        <header class="filterHeader">
          <v-list-item
            class="filterHeaderTitle"
            :prepend-icon="mdiChevronLeft"
            :title="lowerTitle"
            @click="setUIFilterMode('base')"
          />
          <v-list-item
            v-if="isClearable"
            density="compact"
            class="clearFilter"
            title="Clear Filter"
            :append-icon="mdiCloseCircleOutline"
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
        </header>
        <!--
          Age Rating: dual-tab UI. The "Standardized" tab (metron
          values) is selected by default; "As tagged" holds raw
          values with no metron mapping. When there are no
          unstandardized values the tab bar is hidden and only the
          Standardized list renders. A tab shows a primary-colored
          checkbox icon when its filter has any selections. The
          shared search box at the top filters both tabs' items at
          once; if matches land only in the other tab, the view
          switches to it.
        -->
        <template v-if="isAgeRating">
          <v-tabs
            v-if="hasUnstandardizedTagged"
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

import { NULL_PKS, toVuetifyItems } from "@/vuetify-items";
import BrowserFilterChoiceList from "@/components/browser/toolbars/top/filter-choice-list.vue";
import { useBrowserStore } from "@/stores/browser";

const FILTER_TITLE_OVERRIDES = {
  ageRatingMetron: "Age Rating",
};
// Tab values are the filter keys; "Standardized" is the default tab.
const AGE_RATING_DEFAULT_TAB = "ageRatingMetron";

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
     * The As-tagged panel exposes raw ComicInfo age-rating strings that
     * have NO Metron mapping. Strip out:
     *   - entries that already carry a ``metronName`` — the Standardized
     *     panel covers them
     *   - the ``None`` sentinel (``pk`` in ``NULL_PKS``) — Standardized
     *     surfaces it too, so showing it again here is just clutter
     * Returns ``undefined`` until the choices have loaded so the panel
     * can stay hidden during the fetch instead of flashing an empty list.
     */
    unstandardizedTaggedChoices() {
      if (!Array.isArray(this.taggedChoices)) return undefined;
      return this.taggedChoices.filter(
        (c) => !c?.metronName && !NULL_PKS.has(c?.pk),
      );
    },
    hasUnstandardizedTagged() {
      const list = this.unstandardizedTaggedChoices;
      return Array.isArray(list) && list.length > 0;
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
      if (this.hasUnstandardizedTagged) {
        panels.push({
          key: "ageRatingTagged",
          label: "As tagged",
          choices: this.unstandardizedTaggedChoices,
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
      if (!this.isAgeRating || !this.hasUnstandardizedTagged || !val) {
        return;
      }
      /*
       * Switch tabs based on where the search has matches: if matches
       * are exclusive to the other tab, jump to it so the user isn't
       * staring at an empty list. With matches in both (or neither)
       * tab, or when the search is cleared, stay on the current tab.
       */
      const metronMatches = this._countMatches(this.metronChoices, val);
      const taggedMatches = this._countMatches(
        this.unstandardizedTaggedChoices,
        val,
      );
      if (taggedMatches > 0 && metronMatches === 0) {
        this.activeTab = "ageRatingTagged";
      } else if (metronMatches > 0 && taggedMatches === 0) {
        this.activeTab = AGE_RATING_DEFAULT_TAB;
      }
    },
    hasUnstandardizedTagged(val) {
      // The As-tagged tab can vanish after a clear or re-filter;
      // don't leave the window pointed at a tab that no longer exists.
      if (!val) {
        this.activeTab = AGE_RATING_DEFAULT_TAB;
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
      if (mode === "base") {
        return;
      }
      if (typeof this.choices !== "object") {
        this.loadFilterChoices(mode);
      }
      /*
       * Entering Age Rating: also kick off the tagged-choices fetch
       * so the As-tagged panel can render without its own loading
       * state when the user expands it.
       */
      if (this.isAgeRating && typeof this.taggedChoices !== "object") {
        this.loadFilterChoices("ageRatingTagged");
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
      this.$emit("selected", { filters: { [this.name]: value } });
    },
    onAgeRatingSelected(key, value) {
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
.filterHeaderTitle :deep(.v-list-item__prepend > .v-list-item__spacer) {
  display: none;
}

.filterHeaderTitle :deep(.v-list-item-title) {
  font-variant: small-caps;
  color: rbg(var(--v-theme-textDisabled));
  font-weight: bold;
  font-size: 1.6rem !important;
}

.filterValuesProgress {
  margin: 10px;
  width: 88%;
}

.clearFilter {
  color: black;
  background-color: rgb(var(--v-theme-primary));
  opacity: 0.7;
}

.clearFilter:hover {
  opacity: 1;
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
</style>

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
          />
          <v-progress-linear
            v-else
            class="filterValuesProgress"
            rounded
            indeterminate
          />
        </header>
        <!--
          Age Rating: dual-panel UI. The "Standardized" panel (metron
          values) is open by default; "As tagged" is collapsed. Either
          panel header shows a primary-colored checkbox icon when its
          filter has any selections. The shared search box at the top
          filters items in both panels at once; if matches land only
          in the collapsed panel, that panel auto-expands.
        -->
        <v-expansion-panels
          v-if="isAgeRating"
          v-model="expandedPanels"
          multiple
          variant="accordion"
          flat
          class="ageRatingPanels"
        >
          <v-expansion-panel
            v-for="panel of ageRatingPanels"
            :key="panel.key"
            :value="panel.key"
            eager
          >
            <v-expansion-panel-title
              class="ageRatingPanelTitle"
              :class="{ ageRatingPanelTitleActive: panel.hasSelections }"
            >
              {{ panel.label }}
            </v-expansion-panel-title>
            <v-expansion-panel-text>
              <BrowserFilterChoiceList
                :name="panel.key"
                :choices="panel.choices"
                :filter="panel.filter"
                :search="search"
                @selected="(v) => onAgeRatingSelected(panel.key, v)"
              />
            </v-expansion-panel-text>
          </v-expansion-panel>
        </v-expansion-panels>
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
  mdiChevronLeft,
  mdiChevronRight,
  mdiChevronRightCircle,
  mdiCloseCircleOutline,
} from "@mdi/js";
import { mapActions, mapState, mapWritableState } from "pinia";
import { capitalCase } from "text-case";

import { toVuetifyItems } from "@/api/v3/vuetify-items";
import BrowserFilterChoiceList from "@/components/browser/toolbars/top/filter-choice-list.vue";
import { useBrowserStore } from "@/stores/browser";

const FILTER_TITLE_OVERRIDES = {
  ageRatingMetron: "Age Rating",
};
/*
 * Default: only the "Standardized" panel is expanded. Identified
 * by its panel value (the filter key).
 */
const AGE_RATING_DEFAULT_EXPANDED = Object.freeze(["ageRatingMetron"]);

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
      mdiChevronLeft,
      mdiCloseCircleOutline,
      search: "",
      expandedPanels: [...AGE_RATING_DEFAULT_EXPANDED],
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
    ageRatingPanels() {
      return [
        {
          key: "ageRatingMetron",
          label: "Standardized",
          choices: this.metronChoices,
          filter: this.metronFilter,
          hasSelections: this.metronHasSelections,
        },
        {
          key: "ageRatingTagged",
          label: "As tagged",
          choices: this.taggedChoices,
          filter: this.taggedFilter,
          hasSelections: this.taggedHasSelections,
        },
      ];
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
      if (!this.isAgeRating) {
        return;
      }
      /*
       * Auto-expand panels based on where the search has matches. With
       * an empty search we revert to the default (Standardized open,
       * As tagged closed). With a non-empty search, expand whichever
       * panel(s) contain matches; if matches are exclusive to one
       * panel, only that one stays open.
       */
      if (!val) {
        this.expandedPanels = [...AGE_RATING_DEFAULT_EXPANDED];
        return;
      }
      const metronMatches = this._countMatches(this.metronChoices, val);
      const taggedMatches = this._countMatches(this.taggedChoices, val);
      if (metronMatches > 0 && taggedMatches > 0) {
        this.expandedPanels = ["ageRatingMetron", "ageRatingTagged"];
      } else if (taggedMatches > 0) {
        this.expandedPanels = ["ageRatingTagged"];
      } else {
        /*
         * Either standardized-only matches or no matches anywhere —
         * honor the default so the user isn't presented with an
         * empty open panel below an empty closed one.
         */
        this.expandedPanels = [...AGE_RATING_DEFAULT_EXPANDED];
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
      this.expandedPanels = [...AGE_RATING_DEFAULT_EXPANDED];
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

.ageRatingPanels {
  /*
   * v-expansion-panels defaults to a max-width and a fair bit of
   * horizontal padding inside the menu — strip both so the panels
   * fill the sub-menu width like the regular filter list does.
   */
  background: transparent;
}

.ageRatingPanelTitle {
  min-height: 36px;
  padding: 4px 16px;
  font-size: 0.875rem;
}

/*
 * Indicate that a panel has selections by ringing its expansion
 * caret in the primary (orange) theme color. ``box-shadow`` over a
 * border so the ring sits *outside* the icon's hit area without
 * resizing the icon container or shifting the title's baseline.
 */
.ageRatingPanelTitleActive :deep(.v-expansion-panel-title__icon) {
  border-radius: 50%;
  box-shadow: 0 0 0 2px rgb(var(--v-theme-primary));
}

.ageRatingPanels :deep(.v-expansion-panel-text__wrapper) {
  /*
   * Eliminate the default content padding so the inner choice
   * list aligns flush with the rest of the sub-menu's items.
   */
  padding: 0;
}
</style>

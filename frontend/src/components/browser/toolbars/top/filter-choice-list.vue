<template>
  <div>
    <!--
      Static, non-selectable column header above the As-tagged Age
      Rating list. Sits at the right edge of each row so it acts as
      a column heading for the per-item metron mapping shown in the
      append slot below. Suppressed when the list contains a "None"
      row — that row's append slot doubles as the column header.
    -->
    <div
      v-if="showStandaloneTaggedHeader"
      class="taggedColumnHeader"
      aria-hidden="true"
    >
      <span class="metronName">Standardized</span>
    </div>
    <v-list
      :model-value="filter"
      class="filterGroup overflow-y-auto"
      :class="{ filterGroupTightTop: name === 'ageRatingTagged' }"
      density="compact"
      multiple
      @update:selected="$emit('selected', $event)"
    >
      <!--
        Manual ``v-for`` so the per-item ``#append`` slot (used for the
        ``metronName`` annotation in the As-tagged Age Rating panel) can
        render. Passing ``:items=...`` to ``v-list`` would cause Vuetify
        to render each row a second time on top of this loop.
      -->
      <v-list-item
        v-for="item of vuetifyItems"
        :key="item.value"
        density="compact"
        variant="plain"
        :value="item.value"
        :title="itemTitle(item)"
        :active="item.active"
        :disabled="item.active"
        :append-icon="item.icon"
      >
        <template v-if="item.metronName" #append>
          <span class="metronName">{{ item.metronName }}</span>
        </template>
      </v-list-item>
    </v-list>
  </div>
</template>

<script>
import { mdiCheck } from "@mdi/js";
import { mapActions, mapState } from "pinia";

import { toVuetifyItems } from "@/api/v3/vuetify-items";
import { useBrowserStore } from "@/stores/browser";

const NUMERIC_FILTERS = new Set(["decade", "year"]);

export default {
  name: "BrowserFilterChoiceList",
  props: {
    name: {
      type: String,
      required: true,
    },
    choices: {
      type: [Array, Object, Boolean],
      default: () => [],
    },
    filter: {
      type: Array,
      default: () => [],
    },
    search: {
      type: String,
      default: "",
    },
  },
  emits: ["selected"],
  computed: {
    ...mapState(useBrowserStore, {
      readingDirectionTitles: (state) => state.choices.static.readingDirection,
    }),
    isNumeric() {
      return NUMERIC_FILTERS.has(this.name);
    },
    vuetifyItems() {
      /*
       * ``choices`` may be ``true`` (a loading-state placeholder set
       * by the store before ``loadFilterChoices`` resolves) or
       * ``undefined`` if the dynamic filter isn't applicable to the
       * current group. ``toVuetifyItems`` calls ``for...of`` on its
       * ``items``, so anything non-iterable would TypeError; bail out
       * with an empty list and let the parent show its progress
       * indicator until real choices arrive.
       */
      if (!Array.isArray(this.choices)) {
        return [];
      }
      const items =
        this.name === "universes"
          ? this.fixUniverseTitles(this.choices)
          : this.choices;
      const sortBy = this.isNumeric
        ? "numeric"
        : this.name == "ageRatingMetron"
          ? ""
          : this.name == "ageRatingTagged"
            ? "metronIndex"
            : "title";
      const copyKeys =
        this.name === "ageRatingMetron"
          ? ["index"]
          : this.name === "ageRatingTagged"
            ? ["metronName", "index"]
            : [];
      const vItems = toVuetifyItems({
        items,
        filter: this.search,
        sortBy,
        copyKeys,
      });
      for (const item of vItems) {
        item.active = this.filter?.includes(item.value);
        item.icon = item.active ? mdiCheck : undefined;
        /*
         * The "None" row (rendered when comics have no tagged
         * age rating) has no metron mapping of its own — co-opt
         * its append slot as the column heading. The standalone
         * ``taggedColumnHeader`` is suppressed when this fires.
         */
        if (this.name === "ageRatingTagged" && item.title === "None") {
          item.metronName = "Standardized";
        }
      }
      return vItems;
    },
    hasNoneRow() {
      return (
        this.name === "ageRatingTagged" &&
        this.vuetifyItems.some((item) => item.title === "None")
      );
    },
    showStandaloneTaggedHeader() {
      return this.name === "ageRatingTagged" && !this.hasNoneRow;
    },
  },
  methods: {
    ...mapActions(useBrowserStore, [
      "fixUniverseTitles",
      "identifierSourceTitle",
    ]),
    itemTitle(item) {
      if (this.name === "readingDirection") {
        return this.readingDirectionTitles[item.value];
      } else if (this.name === "identifierSource") {
        return this.identifierSourceTitle(item.title);
      }
      return item.title;
    },
  },
};
</script>

<style scoped lang="scss">
.filterGroup {
  max-height: 80vh;
  /* has to be less than the menu height */
}

.metronName {
  /*
   * Pre-existing typo (``rbg`` vs ``rgb``) made the color rule
   * invalid so both the right-side per-row metron annotations and
   * the standalone column header fell back to whatever color the
   * surrounding parent inherited — different parents, so they
   * didn't visually match. Explicit ``rgb`` here pins them to the
   * codex theme's ``textDisabled`` token.
   */
  color: rgb(var(--v-theme-textDisabled));
  opacity: 0.7;
  text-align: right;
  font-size: smaller;
}

.taggedColumnHeader {
  /*
   * Right-align the header text so it sits above the per-row
   * ``metronName`` cells. Padding mirrors the v-list-item's right
   * padding so the column line is consistent. No bottom padding —
   * the v-list below is set to ``padding-top: 0`` so the header
   * and the first row sit flush.
   */
  display: flex;
  justify-content: flex-end;
  padding: 4px 16px 0 0;
}

/*
 * Strip the v-list's default top padding so the As-tagged list
 * sits flush against either the standalone column header or the
 * "None" row that doubles as a column header.
 */
.filterGroupTightTop {
  padding-top: 0;
}
</style>

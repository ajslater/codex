<template>
  <div @keydown.capture="onKeydownCapture" @keydown="onKeydown">
    <v-list class="filterGroup overflow-y-auto" density="compact">
      <!--
        Manual ``v-for`` instead of ``:items=...`` — Vuetify would
        render each row a second time on top of this loop. Also needed
        for the per-item ``#prepend`` slot. Each row is a checkbox that
        toggles its value, as the released Shelves sub-menu did; the
        list has no selection model of its own. The As-tagged tab puts
        the standardized age rating in a column after the checkbox,
        empty for unmapped tags, so the raw tags stay aligned.
      -->
      <v-list-item
        v-for="item of vuetifyItems"
        :key="item.value"
        class="filterChoice"
        :class="{ filterChoiceTicked: item.ticked }"
        density="compact"
        variant="plain"
        role="menuitemcheckbox"
        :aria-checked="String(item.ticked)"
        :title="itemTitle(item)"
        @click="onToggle(item)"
      >
        <template #prepend>
          <v-checkbox-btn
            density="compact"
            :model-value="item.ticked"
            tabindex="-1"
            readonly
          />
          <span v-if="name === 'ageRatingTagged'" class="metronName">{{
            item.metronName
          }}</span>
        </template>
      </v-list-item>
    </v-list>
  </div>
</template>

<script>
import { mapActions, mapState } from "pinia";

import { toVuetifyItems } from "@/vuetify-items";
import { useBrowserStore } from "@/stores/browser";

/*
 * Filters whose choices come in an order that means something: Metron's
 * age ratings by age, reading lists with your own first, and the reading
 * list kinds as Mine, Curated, From Tags.
 */
const SERVER_ORDERED_FILTERS = new Set([
  "ageRatingMetron",
  "readingListKind",
  "readingLists",
]);
/*
 * Filters whose order is the point, so ticked rows do not jump ahead:
 * the age ratings by age, the reading list kinds as Mine, Curated, From
 * Tags. Reading lists do bring ticked lists first.
 */
const FIXED_ORDER_FILTERS = Object.freeze(
  new Set(["ageRatingMetron", "ageRatingTagged", "readingListKind"]),
);
// Keys a VList moves focus with.
const NAVIGATION_KEYS = Object.freeze(
  new Set(["ArrowDown", "ArrowUp", "Home", "End"]),
);
const NUMERIC_FILTERS = new Set([
  "decade",
  "seriesEndYear",
  "seriesStartYear",
  "year",
]);

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
  data() {
    return {
      /*
       * The values ticked when the list opened. They come first, and
       * stay where they are as you tick, so rows don't jump under the
       * pointer.
       */
      tickedOnOpen: new Set(this.filter),
      // The row focused before a navigation key, while it is handled.
      focusBefore: undefined,
    };
  },
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
        : SERVER_ORDERED_FILTERS.has(this.name)
          ? ""
          : this.name == "ageRatingTagged"
            ? "index"
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
      const ticked = new Set(this.filter);
      for (const item of vItems) {
        item.ticked = ticked.has(item.value);
      }
      if (FIXED_ORDER_FILTERS.has(this.name) || !this.tickedOnOpen.size) {
        return vItems;
      }
      const isFirst = (item) => this.tickedOnOpen.has(item.value);
      return [
        ...vItems.filter((item) => isFirst(item)),
        ...vItems.filter((item) => !isFirst(item)),
      ];
    },
  },
  methods: {
    ...mapActions(useBrowserStore, [
      "fixUniverseTitles",
      "identifierSourceTitle",
    ]),
    onKeydownCapture(event) {
      this.focusBefore = NAVIGATION_KEYS.has(event.key)
        ? document.activeElement
        : undefined;
    },
    onKeydown(event) {
      /*
       * This list sits inside the select's own list, and a VList moves
       * focus without stopping the key, so each arrow stepped two rows.
       * Once this list has moved one row, the key stops here. At either
       * end this list would wrap; put focus back and let the menu's list
       * step out of the choices instead.
       */
      const before = this.focusBefore;
      this.focusBefore = undefined;
      if (!before) {
        return;
      }
      const rows = [...this.$el.querySelectorAll("[role=menuitemcheckbox]")];
      const from = rows.indexOf(before);
      const to = rows.indexOf(document.activeElement);
      if (from === -1 || to === -1) {
        return;
      }
      const wrapped =
        (event.key === "ArrowDown" && to < from) ||
        (event.key === "ArrowUp" && to > from);
      if (wrapped) {
        before.focus({ preventScroll: true });
        return;
      }
      event.stopPropagation();
    },
    onToggle(item) {
      /*
       * From the whole filter, not the rows shown: a ticked value the
       * search box hides stays ticked.
       */
      const filter = this.filter || [];
      const next = filter.includes(item.value)
        ? filter.filter((value) => value !== item.value)
        : [...filter, item.value];
      this.$emit("selected", next);
    },
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
/* Layered: these rules beat Vuetify's component CSS by position,
 * and lose to a `color`/utility prop, which is the intended order. */
@layer codex-components {
  .filterGroup {
    max-height: 80vh;
    /* has to be less than the menu height */
  }

  /*
   * Plain rows sit at 0.62 opacity unless hovered or focused; a ticked
   * row reads at full strength, like the one last clicked.
   */
  .filterChoiceTicked {
    opacity: 1;
  }

  .metronName {
    /*
     * The standardized (metron) equivalent of a raw tagged age
     * rating, in a left column before the raw tag. Fixed width so
     * the raw tags align into their own column ("Teen Plus", the
     * longest value, is 9ch). ``text-disabled`` is too dim against
     * the dark menu surface, so use ``on-surface`` dimmed by
     * opacity instead.
     */
    width: 10ch;
    color: rgb(var(--v-theme-on-surface));
    opacity: 0.7;
    font-size: smaller;
  }

  /*
   * Vuetify puts a 32px spacer between a list item's prepend and its
   * content; the checkbox, and the standardized column with its fixed
   * width, already pad themselves, so tighten the gap.
   */
  .filterGroup :deep(.v-list-item__prepend > .v-list-item__spacer) {
    width: 8px;
  }
}
</style>

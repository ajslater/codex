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
        :disabled="item.blocked"
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
        <template v-if="item.reason" #append>
          <span class="filterChoiceReason">{{ item.reason }}</span>
        </template>
      </v-list-item>
    </v-list>
  </div>
</template>

<script>
import { mapActions, mapState } from "pinia";

import { VUETIFY_NULL_CODE } from "@/choices/browser-choices.json";
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
// Under All, None cannot be ticked with other values; its row says so.
const NONE_UNDER_ALL_REASON = "Not with Match all";
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
    // The filter matches all ticked values, not any.
    matchAll: {
      type: Boolean,
      default: false,
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
      /*
       * Every row shown since the list opened, in its place. Under All a
       * refresh never removes one, which would move rows under the
       * pointer: a row no longer offered dims instead, and rows newly
       * offered go after. They drop out when the list opens again.
       */
      keptItems: [],
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
    offeredItems() {
      /*
       * The choices on offer now as rows, sorted, before the search box.
       * ``choices`` may be ``true`` (a loading-state placeholder set by
       * the store before ``loadFilterChoices`` resolves) or ``undefined``
       * if the dynamic filter isn't applicable to the current group;
       * either is no rows, and the parent shows its progress indicator
       * until real choices arrive.
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
      return toVuetifyItems({ items, sortBy, copyKeys });
    },
    vuetifyItems() {
      const offered = this.offeredItems;
      const offeredValues = new Set(offered.map((item) => item.value));
      const ticked = new Set(this.filter);
      const search = this.search?.toLowerCase();
      const shown = [];
      for (const source of this.matchAll ? this.keptItems : offered) {
        if (search && !source.title.toLowerCase().includes(search)) {
          continue;
        }
        shown.push(this._row(source, ticked, offeredValues));
      }
      if (FIXED_ORDER_FILTERS.has(this.name) || !this.tickedOnOpen.size) {
        return shown;
      }
      const isFirst = (item) => this.tickedOnOpen.has(item.value);
      return [
        ...shown.filter((item) => isFirst(item)),
        ...shown.filter((item) => !isFirst(item)),
      ];
    },
  },
  watch: {
    offeredItems: {
      immediate: true,
      handler(items) {
        const kept = new Set(this.keptItems.map((item) => item.value));
        const added = items.filter((item) => !kept.has(item.value));
        if (added.length) {
          this.keptItems = [...this.keptItems, ...added];
        }
      },
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
    _row(source, ticked, offeredValues) {
      /*
       * One row to show. Under All a row is not tickable when it no
       * longer occurs with the ticked values, or is None, which cannot
       * combine with them. A ticked row is never blocked, so it can be
       * unticked.
       */
      const item = { ...source, ticked: ticked.has(source.value) };
      if (!this.matchAll || item.ticked) {
        return item;
      }
      const isNone = item.value === VUETIFY_NULL_CODE;
      item.blocked = isNone || !offeredValues.has(item.value);
      if (isNone) {
        item.reason = NONE_UNDER_ALL_REASON;
      }
      return item;
    },
    onToggle(item) {
      if (item.blocked) {
        return;
      }
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

  .filterChoiceReason {
    color: rgb(var(--v-theme-on-surface));
    font-size: smaller;
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

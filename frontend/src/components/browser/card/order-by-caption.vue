<template>
  <!-- eslint-disable vue/no-v-html, sonarjs/no-vue-bypass-sanitization -->
  <div
    v-if="orderValue"
    class="orderCaption text-caption"
    v-html="orderValue"
  />
  <!--eslint-enable-->
</template>
<script>
import { mapState } from "pinia";
import prettyBytes from "pretty-bytes";

import { DATE_FORMAT, getDateTime, NUMBER_FORMAT } from "@/datetime";
import { useBrowserStore } from "@/stores/browser";
const STAR_SORT_BY = new Set(["critical_rating"]);
const DATE_SORT_BY = new Set(["date"]);
const TIME_SORT_BY = new Set([
  "bookmark_updated_at",
  "created_at",
  "metadata_mtime",
  "updated_at",
]);

const HIDE_ORDER_BYS = new Set([null, undefined, "sort_name"]);
const HIDE_ORDER_VALUES = new Set([null, undefined]);

export default {
  name: "OrderByCaption",
  props: {
    item: {
      type: Object,
      required: true,
    },
  },
  computed: {
    ...mapState(useBrowserStore, {
      orderBy: (state) => state.settings.orderBy,
      twentyFourHourTime: (state) => state.settings.twentyFourHourTime,
      topGroup: (state) => state.settings.topGroup,
    }),
    orderValue() {
      const ov = this.item.orderValue;
      /*
       * Hot path: this computed runs once per card per render
       * (typically 100 cards on a browser page) and the
       * overwhelmingly common case is ``orderBy`` = ``sort_name``
       * which produces an empty caption. Bail before allocating
       * a try/catch frame and walking the type-specific dispatch
       * below.
       */
      if (HIDE_ORDER_BYS.has(this.orderBy)) return "";
      if (HIDE_ORDER_VALUES.has(ov)) return "";
      if (this.orderBy === "filename" && this.item.group !== "c") return "";
      if (this.orderBy === "story_arc_number" && this.item.group === "a") {
        return "";
      }
      try {
        if (DATE_SORT_BY.has(this.orderBy)) {
          const date = new Date(ov);
          return DATE_FORMAT.format(date);
        } else if (this.orderBy === "search_score") {
          return this.format_search_score(ov);
        } else if (TIME_SORT_BY.has(this.orderBy)) {
          // This is what needs v-html to work with the embedded break.
          return getDateTime(ov, this.twentyFourHourTime, true);
        } else if (this.orderBy === "page_count") {
          return `${NUMBER_FORMAT.format(ov)} pages`;
        } else if (this.orderBy === "size") {
          return prettyBytes(Number.parseInt(ov, 10));
        } else if (STAR_SORT_BY.has(this.orderBy)) {
          return `★  ${this.formatStarRating(ov)}`;
        }
      } catch (error) {
        // Often orderBy gets updated before orderValue gets returned.
        console.debug(error);
      }
      return ov;
    },
  },
  methods: {
    format_search_score(ov) {
      // Round Whoosh float into a two digit integer.
      ov = NUMBER_FORMAT.format(Math.round(Number.parseFloat(ov) * 10));
      if (Number.isNaN(ov)) {
        ov = "";
      }
      return ov;
    },
    /*
     * Critical-rating order_value is a DecimalField aggregate that
     * arrives as a string like "8.5000" or "9.00". Render with at most
     * two fractional digits and no trailing zeros so the caption shows
     * "8.5" / "9", not "8.5000" / "9.00".
     */
    formatStarRating(ov) {
      const n = Number.parseFloat(ov);
      if (!Number.isFinite(n)) return ov;
      return n.toFixed(2).replace(/\.?0+$/, "");
    },
  },
};
</script>

<style scoped lang="scss">
.orderCaption {
  color: rgb(var(--v-theme-textDisabled));
  text-align: center;
}
</style>

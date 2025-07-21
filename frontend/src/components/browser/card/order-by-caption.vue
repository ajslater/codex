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
      let ov = this.item.orderValue;
      try {
        if (
          HIDE_ORDER_BYS.has(this.orderBy) ||
          (this.orderBy === "filename" && this.item.group !== "c") ||
          (this.orderBy === "story_arc_number" && this.item.group === "a") ||
          HIDE_ORDER_VALUES.has(ov)
        ) {
          ov = "";
        } else if (DATE_SORT_BY.has(this.orderBy)) {
          const date = new Date(ov);
          ov = DATE_FORMAT.format(date);
        } else if (this.orderBy == "search_score") {
          ov = this.format_search_score(ov);
        } else if (TIME_SORT_BY.has(this.orderBy)) {
          // this is what needs v-html to work with the embedded break.
          ov = getDateTime(ov, this.twentyFourHourTime, true);
        } else if (this.orderBy == "page_count") {
          const human = NUMBER_FORMAT.format(ov);
          ov = `${human} pages`;
        } else if (this.orderBy == "size") {
          ov = prettyBytes(Number.parseInt(ov, 10));
        } else if (STAR_SORT_BY.has(this.orderBy)) {
          ov = `★  ${ov}`;
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
  },
};
</script>

<style scoped lang="scss">
.orderCaption {
  color: rgb(var(--v-theme-textDisabled));
  text-align: center;
}
</style>

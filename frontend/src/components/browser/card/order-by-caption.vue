<template>
  <!-- eslint-disable vue/no-v-html -->
  <div
    v-if="orderValue"
    class="orderCaption text-caption"
    v-html="orderValue"
  />
  <!--eslint-enable-->
</template>
<script>
import humanize from "humanize";
import { mapState } from "pinia";

import { DATE_FORMAT, getDateTime } from "@/datetime";
import { useBrowserStore } from "@/stores/browser";
const STAR_SORT_BY = new Set(["community_rating", "critical_rating"]);
const DATE_SORT_BY = new Set(["date"]);
const TIME_SORT_BY = new Set(["created_at", "updated_at"]);

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
    }),
    orderValue() {
      let ov = this.item.orderValue;
      if (
        this.orderBy === undefined ||
        this.orderBy === null ||
        this.orderBy === "sort_name" ||
        (this.orderBy === "path" && this.item.group === "f") ||
        ov === null ||
        ov === undefined
      ) {
        ov = "";
      } else if (DATE_SORT_BY.has(this.orderBy)) {
        const date = new Date(ov);
        ov = DATE_FORMAT.format(date);
      } else if (this.orderBy == "search_score") {
        // Round Whoosh float into a two digit integer.
        ov = Math.round(Number.parseFloat(ov) * 10);
      } else if (TIME_SORT_BY.has(this.orderBy)) {
        // this is what needs v-html to work with the embedded break.
        ov = getDateTime(ov, this.twentyFourHourTime, true);
      } else if (this.orderBy == "page_count") {
        const human = humanize.numberFormat(Number.parseInt(ov, 10), 0);
        ov = `${human} pages`;
      } else if (this.orderBy == "size") {
        ov = humanize.filesize(Number.parseInt(ov, 10), 1024, 1);
      } else if (STAR_SORT_BY.has(this.orderBy)) {
        ov = `★  ${ov}`;
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

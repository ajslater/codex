<template>
  <router-link
    :to="route"
    :aria-label="label"
    :class="{
      [pageChangeClass]: true,
      [directionClass]: true,
    }"
    @click="$event.stopImmediatePropagation()"
  />
</template>
<script>
import { mapActions, mapState } from "pinia";

import { getComicPageSource } from "@/api/v3/reader";
import { linksInfo } from "@/components/reader/prefetch-links";
import { useReaderStore } from "@/stores/reader";

export default {
  name: "PageChangeLink",
  props: {
    direction: { type: String, required: true },
  },
  head() {
    return linksInfo([this.prefetchSrc1, this.prefetchSrc2]);
  },
  computed: {
    ...mapState(useReaderStore, {
      params(state) {
        return state.routes[this.computedDirection];
      },
      prefetchSrc2(state) {
        const book = state.books.get(this.params.pk);
        if (!book) {
          return false;
        }
        const settings = this.getSettings(book);
        if (!settings.twoPages) {
          return false;
        }
        const paramsPlus = { ...this.params, page: this.params.page + 1 };
        if (paramsPlus.page > book.maxPage) {
          return false;
        }
        return getComicPageSource(paramsPlus);
      },
      directionClass(state) {
        let dc = this.direction;
        if (state.activeSettings.vertical) {
          dc += "Vertical";
        }
        return dc;
      },
      pageChangeClass(state) {
        let pcc = "pageChange";
        pcc += state.activeSettings.vertical ? "Row" : "Column";
        return pcc;
      },
    }),
    computedDirection() {
      return this.normalizeDirection(this.direction);
    },
    prefetchSrc1() {
      return this.params ? getComicPageSource(this.params) : false;
    },
    route() {
      return this.params ? { params: this.params } : {};
    },
    label() {
      const prefix = this.computedDirection === "prev" ? "Previous" : "Next";
      return `${prefix} Page`;
    },
  },
  methods: {
    ...mapActions(useReaderStore, ["getSettings", "normalizeDirection"]),
  },
};
</script>
<style scoped lang="scss">
.pageChangeColumn {
  position: fixed;
  height: 100%;
  width: 33vw;
}
.pageChangeRow {
  position: fixed;
  height: 33vh;
  width: 100%;
}
.prev {
  left: 0px;
  cursor: w-resize;
}
.prevVertical {
  top: 0px;
  cursor: n-resize;
}
.next {
  right: 0px;
  cursor: e-resize;
}
.nextVertical {
  bottom: 0px;
  cursor: s-resize;
}
</style>

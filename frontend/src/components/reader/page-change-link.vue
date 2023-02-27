<template>
  <router-link
    class="pageChangeColumn"
    :to="route"
    :aria-label="label"
    :class="{
      [direction]: true,
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
        const settings = this.getSettings(state.readerSettings, book);
        if (!settings.twoPages) {
          return false;
        }
        const paramsPlus = { ...this.params, page: this.params.page + 1 };
        if (paramsPlus.page > book.maxPage) {
          return false;
        }
        return getComicPageSource(paramsPlus);
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
  height: 100%;
  width: 33vw;
}
.prev {
  cursor: w-resize;
  left: 0px;
}
.next {
  cursor: e-resize;
  right: 0px;
}
</style>

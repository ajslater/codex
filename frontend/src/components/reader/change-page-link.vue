<template>
  <router-link
    class="pageChangeColumn"
    :to="route"
    :aria-label="label"
    :class="{
      leftArrow: direction === 'prev',
      rightArrow: direction === 'next',
    }"
    @click.native="$event.stopImmediatePropagation()"
  />
</template>
<script>
import { mapActions, mapState } from "pinia";

import { getComicPageSource } from "@/api/v3/reader";
import { useReaderStore } from "@/stores/reader";

const PREFETCH_LINK = { rel: "prefetch", as: "image" };

export default {
  name: "PageChangeLink",
  props: {
    direction: { type: String, required: true },
  },
  head() {
    const links = [];
    if (this.prefetchSrc1) {
      links.push({ ...PREFETCH_LINK, href: this.prefetchSrc1 });
    }
    if (this.prefetchSrc2) {
      links.push({ ...PREFETCH_LINK, href: this.prefetchSrc2 });
    }
    if (links.length > 0) {
      return { link: links };
    }
  },
  computed: {
    ...mapState(useReaderStore, {
      params(state) {
        return state.routes[this.direction];
      },
      prefetchSrc1(state) {
        return this.params
          ? getComicPageSource(this.params, state.timestamp)
          : false;
      },
      prefetchSrc2(state) {
        const book = state.books.get(this.params.pk);
        if (!book) {
          return false;
        }
        const bookSettings = book.settings || {};
        const settings = this.getSettings(state.readerSettings, bookSettings);
        if (!settings.twoPages) {
          return false;
        }
        const paramsPlus = { ...this.params, page: this.params.page + 1 };
        if (paramsPlus.page > book.maxPage) {
          return false;
        }
        return getComicPageSource(paramsPlus, state.timestamp);
      },
    }),
    route() {
      return this.params ? { params: this.params } : {};
    },
    label() {
      const prefix = this.direction === "prev" ? "Previous" : "Next";
      return `${prefix} Page`;
    },
  },
  methods: {
    ...mapActions(useReaderStore, ["getSettings"]),
  },
};
</script>
<style scoped lang="scss">
.pageChangeColumn {
  display: block;
  width: 100%;
  height: 100%;
}
.leftArrow {
  cursor: w-resize;
}
.rightArrow {
  cursor: e-resize;
}
</style>

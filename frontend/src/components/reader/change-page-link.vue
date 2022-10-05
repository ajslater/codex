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
import { mapGetters, mapState } from "pinia";

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
    ...mapGetters(useReaderStore, ["computedSettings"]),
    ...mapState(useReaderStore, {
      route(state) {
        return state.routes && state.routes[this.direction]
          ? { params: state.routes[this.direction] }
          : {};
      },
      maxPage: (state) => state.comic.maxPage,
      prefetchSrc1(state) {
        const route = state.routes[this.direction];
        return route ? getComicPageSource(route, state.timestamp) : false;
      },
      prefetchSrc2(state) {
        if (!this.computedSettings.twoPages) {
          return false;
        }
        const route = { ...state.routes[this.direction] };
        if (!route || +route.page + 1 > this.maxPage) {
          return false;
        }
        route.page += 1;
        return getComicPageSource(route, state.timestamp);
      },
    }),
    label() {
      const prefix = this.direction === "prev" ? "Previous" : "Next";
      return `${prefix} Page`;
    },
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

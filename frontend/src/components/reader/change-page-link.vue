<template>
  <router-link
    class="pageChangeColumn"
    :to="route"
    :aria-label="label"
    :class="{
      leftArrow: direction === 'prev',
      rightArrow: direction === 'next',
    }"
  />
</template>
<script>
import { mapState } from "pinia";

import { getComicPageSource } from "@/api/v3/reader";
import { useReaderStore } from "@/stores/reader";
export default {
  name: "PageChangeLink",
  props: {
    direction: { type: String, required: true },
  },
  head() {
    if (this.prefetchSrc) {
      return { link: { rel: "prefetch", as: "image", href: this.prefetchSrc } };
    }
  },
  computed: {
    ...mapState(useReaderStore, {
      route(state) {
        return state.routes && state.routes[this.direction]
          ? { params: state.routes[this.direction] }
          : {};
      },
      prefetchSrc(state) {
        const routes = state.routes;
        return routes[this.direction]
          ? getComicPageSource(routes[this.direction], state.timestamp)
          : false;
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

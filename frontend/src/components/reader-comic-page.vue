<template>
  <img
    v-if="displayPage"
    class="page"
    :class="fitToClass"
    :src="src"
    :alt="alt"
  />
</template>

<script>
import { mapGetters, mapState } from "vuex";

import { getComicPageSource } from "@/api/v2/comic";

export default {
  name: "ReaderComicPage",
  props: {
    pageIncrement: {
      type: Number,
      required: true,
    },
  },
  head() {
    if (!this.displayPage || !this.nextRoute) {
      return;
    }
    return { link: [{ rel: "prefetch", as: "image", href: this.nextSrc }] };
  },
  computed: {
    ...mapState("reader", {
      page: function (state) {
        return state.routes.current.page + this.pageIncrement;
      },
      maxPage: (state) => state.maxPage,
      currentRoute: (state) => state.routes.current,
      nextRoute: (state) => state.routes.next,
    }),
    ...mapGetters("reader", ["computedSettings"]),
    displayPage() {
      return (
        (this.pageIncrement === 0 || this.computedSettings.twoPages) &&
        this.page <= this.maxPage &&
        this.page >= 0
      );
    },
    src() {
      const route = { ...this.currentRoute };
      route.page = this.page;
      return getComicPageSource(route);
    },
    nextSrc() {
      const route = { ...this.nextRoute };
      route.page = this.nextRoute.page + this.pageIncrement;
      return getComicPageSource(route);
    },
    alt() {
      return `Page ${this.page}`;
    },
    fitToClass() {
      let cls = "";
      const fitTo = this.computedSettings.fitTo;
      if (fitTo) {
        cls = "fitTo";
        cls += fitTo.charAt(0).toUpperCase();
        cls += fitTo.slice(1).toLowerCase();
        if (this.computedSettings.twoPages) {
          cls += "Two";
        }
      }
      return cls;
    },
  },
};
</script>

<style scoped lang="scss">
.page {
  flex: 0 0 auto;
  /* align-self fixes mobile safari stretching the image weirdly */
  align-self: flex-start;
}
.fitToHeight,
.fitToHeightTwo {
  max-height: 100vh;
}
.fitToWidth {
  max-width: 100vw;
}
.fitToWidthTwo {
  max-width: 50vw;
}
</style>

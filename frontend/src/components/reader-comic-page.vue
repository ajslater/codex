<template>
  <img v-if="displayPage" :class="fitToClass" :src="src" :alt="alt" />
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
  data() {
    return {
      page: 0,
    };
  },
  head() {
    if (this.displayPage && this.nextRoute) {
      return { link: [{ rel: "prefetch", as: "image", href: this.nextSrc }] };
    }
  },
  computed: {
    ...mapState("reader", {
      maxPage: (state) => state.maxPage,
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
      const routeParams = { ...this.$router.currentRoute.params };
      routeParams.page = this.page;
      return getComicPageSource(routeParams);
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
      let classes = { page: true };
      const fitTo = this.computedSettings.fitTo;
      if (fitTo) {
        let fitToClass = "fitTo";
        fitToClass += fitTo.charAt(0).toUpperCase();
        fitToClass += fitTo.slice(1).toLowerCase();
        if (this.computedSettings.twoPages) {
          fitToClass += "Two";
        }
        classes[fitToClass] = true;
      }
      return classes;
    },
  },
  watch: {
    $route: function () {
      this.setPage();
    },
  },
  created: function () {
    this.setPage();
  },
  methods: {
    setPage: function () {
      // This can't be computed because router params aren't reactive.
      this.page =
        Number(this.$router.currentRoute.params.page) + this.pageIncrement;
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

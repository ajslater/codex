<template>
  <vue-pdf-embed
    :key="pdfKey"
    :class="fitToClass"
    :source="src"
    :page="page"
    :width="pdfWidth"
    :height="pdfHeight"
    :disable-annotation-layer="true"
    :disable-text-layer="true"
  />
</template>

<script>
import { mapGetters, mapState } from "pinia";
import VuePdfEmbed from "vue-pdf-embed/dist/vue2-pdf-embed";

import { getComicPageSource } from "@/api/v3/reader";
import { useReaderStore } from "@/stores/reader";

export default {
  name: "PDFReader",
  components: { VuePdfEmbed },
  data() {
    return {
      page: 0,
    };
  },
  computed: {
    ...mapState(useReaderStore, {
      maxPage: (state) => state.comic.maxPage,
      nextRoute: (state) => state.routes.next,
      timestamp: (state) => state.timestamp,
    }),
    ...mapGetters(useReaderStore, ["computedSettings"]),
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
      return getComicPageSource(routeParams, this.timestamp);
    },
    nextSrc() {
      const route = { ...this.nextRoute };
      route.page = this.nextRoute.page + this.pageIncrement;
      return getComicPageSource(route, this.timestamp);
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
    pdfWidth() {
      // Wide PDFs will not fit to SCREEN well.
      // vue-pdf-embed internal canvas sizing algorithm makes this difficult.
      // Maybe not impossible but I'm lazy right now.
      const fitTo = this.computedSettings.fitTo;
      let width = 0;
      if (["WIDTH", "ORIG"].includes(fitTo)) {
        width = window.innerWidth;
      }
      if (width && this.computedSettings.twoPages) {
        width = width / 2;
      }
      return width;
    },
    pdfHeight() {
      const fitTo = this.computedSettings.fitTo;
      return ["HEIGHT", "SCREEN", "ORIG"].includes(fitTo)
        ? window.innerHeight
        : 0;
    },
    pdfKey() {
      return `${this.computedSettings.fitTo}${this.computedSettings.twoPages}`;
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
      // page can't be computed because router params aren't reactive.
      this.page = Number(this.$router.currentRoute.params.page);
    },
  },
};
</script>

<style scoped lang="scss">
.fitToScreen,
.fitToScreenTwo,
.fitToHeight,
.fitToHeightTwo {
  height: 100vh;
}
.fitToScreen,
.fitToWidth {
  width: 100vw;
}
.fitToScreenTwo,
.fitToWidthTwo {
  width: 50vw;
}
.fitToOrig,
.fitToOrigTwo {
  object-fit: none;
}
</style>

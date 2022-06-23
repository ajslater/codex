<template>
  <div v-if="displayPage" :id="page">
    <Placeholderplaceholder
      class="placeholder"
      :size="placeholderSize"
      :class="{ hidden: loaded }"
    />
    <vue-pdf-embed
      v-if="isPDF"
      :key="pdfKey"
      :class="fitToClass"
      :source="src"
      :page="1"
      :width="pdfWidth"
      :height="pdfHeight"
      :disable-annotation-layer="true"
      :disable-text-layer="true"
      @load="imgLoaded"
    />
    <img v-else :class="fitToClass" :src="src" :alt="alt" @load="imgLoaded" />
  </div>
</template>

<script>
import VuePdfEmbed from "vue-pdf-embed/dist/vue2-pdf-embed";
import { mapGetters, mapState } from "vuex";

import { getComicPageSource } from "@/api/v2/comic";
import Placeholderplaceholder from "@/components/placeholder-loading";

const PLACEHOLDER_ENGAGE_MS = 500;

export default {
  name: "ReaderComicPage",
  components: { Placeholderplaceholder, VuePdfEmbed },
  props: {
    pageIncrement: {
      type: Number,
      required: true,
    },
  },
  data() {
    return {
      page: 0,
      loaded: 0,
    };
  },
  head() {
    if (this.displayPage && this.nextRoute) {
      return { link: [{ rel: "prefetch", as: "image", href: this.nextSrc }] };
    }
  },
  computed: {
    ...mapState("reader", {
      maxPage: (state) => state.comic.maxPage,
      nextRoute: (state) => state.routes.next,
      timestamp: (state) => state.timestamp,
      isPDF: (state) => state.comic.fileFormat === "pdf",
    }),
    ...mapGetters("reader", ["computedSettings"]),
    displayPage() {
      return (
        (this.pageIncrement === 0 || this.computedSettings.twoPages) &&
        this.page <= this.maxPage &&
        this.page >= 0
      );
    },
    placeholderSize() {
      const maxDimension = Math.min(window.innerHeight, window.innerWidth);
      return Number.parseInt(maxDimension / 2);
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
      setTimeout(() => {
        if (Date.now() - this.loaded > PLACEHOLDER_ENGAGE_MS) {
          this.loaded = 0;
        }
      }, PLACEHOLDER_ENGAGE_MS);

      // page can't be computed because router params aren't reactive.
      this.page =
        Number(this.$router.currentRoute.params.page) + this.pageIncrement;
    },
    imgLoaded: function () {
      this.loaded = Date.now();
    },
  },
};
</script>

<style scoped lang="scss">
.page {
  flex: 0 0 auto;
  /* align-self fixes mobile safari stretching the image weirdly */
  align-self: flex-start;
  object-fit: contain;
  display: block;
}
.fitToHeight,
.fitToHeightTwo {
  max-height: 100vh;
}
.fitToScreen,
.fitToScreenTwo {
  height: 100vh;
}
.fitToScreen,
.fitToWidth {
  max-width: 100vw;
}
.fitToScreenTwo,
.fitToWidthTwo {
  width: 50vw;
}
.fitToOrig,
.fitToOrigTwo {
  object-fit: none;
}
.placeholder {
  position: absolute;
  top: 25vh;
  left: 40vw;
}
.hidden {
  display: none;
}
</style>

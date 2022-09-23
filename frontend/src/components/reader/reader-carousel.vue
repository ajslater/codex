<template>
  <div>
    <Placeholder
      class="placeholder"
      :size="placeholderSize"
      :class="{ hidden: loaded }"
    />
    <vue-pdf-embed
      v-if="isPDF"
      :key="pdfKey"
      :class="fitToClass"
      :source="src(0)"
      :page="1"
      :width="pdfWidth"
      :height="pdfHeight"
      :disable-annotation-layer="true"
      :disable-text-layer="true"
      @load="imgLoaded"
    />
    <v-carousel @change="carouselChange">
      <v-carousel-item v-for="page in pages" :key="page" :src="src(page)" />
    </v-carousel>
  </div>
</template>

<script>
import { mapGetters, mapState } from "pinia";
const VuePdfEmbed = () => import("vue-pdf-embed/dist/vue2-pdf-embed");

import { getComicPageSource } from "@/api/v3/reader";
import Placeholder from "@/components/placeholder-loading.vue";
import { useReaderStore } from "@/stores/reader";

//const PLACEHOLDER_ENGAGE_MS = 500;

export default {
  name: "ReaderCarousel",
  components: { Placeholder, VuePdfEmbed },
  props: {},
  data() {
    return {
      pages: [],
      currentPage: 0,
      loaded: 1,
    };
  },
  head() {
    if (this.displayPage && this.nextRoute) {
      return { link: [{ rel: "prefetch", as: "image", href: this.nextSrc }] };
    }
  },
  computed: {
    ...mapState(useReaderStore, {
      maxPage: (state) => state.comic.maxPage,
      nextRoute: (state) => state.routes.next,
      timestamp: (state) => state.timestamp,
      isPDF: (state) => state.comic.fileFormat === "pdf",
    }),
    ...mapGetters(useReaderStore, ["computedSettings"]),
    displayPage() {
      return this.currentPage <= this.maxPage && this.currentPage >= 0;
    },
    placeholderSize() {
      const maxDimension = Math.min(window.innerHeight, window.innerWidth);
      return Number.parseInt(maxDimension / 2);
    },
    nextSrc() {
      const route = { ...this.nextRoute };
      route.page = this.nextRoute.page;
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
    src(page) {
      const routeParams = { ...this.$router.currentRoute.params, page };
      const res = getComicPageSource(routeParams, this.timestamp);
      console.log(res);
      return res;
    },
    setPage: function () {
      // page can't be computed because router params aren't reactive.
      this.currentPage = Number(this.$router.currentRoute.params.page);
      if (!this.pages.includes(this.currentPage)) {
        this.pages.push(this.currentPage);
      }
      const nextPage = this.currentPage + 1;
      if (nextPage <= this.maxPage && !this.pages.includes(nextPage)) {
        this.pages.push(this.currentPage + 1);
      }
      this.pages.sort();
    },
    carouselChange(page) {
      console.log({ page });
      const params = {
        ...this.$router.currentRoute.params,
        page,
      };
      console.log({ params });
      this.$router.push({ params });
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
.placeholder {
  position: absolute;
  top: 50%;
  left: 50%;
  transform: translate(-50%, -50%);
}
.hidden {
  display: none;
}
</style>

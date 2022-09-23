<template>
  <div>
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
    <v-window v-else v-model="currentPage" @change="change">
      <v-window-item v-for="page in pages" :key="page" @click="click">
        <v-card>
          <img :src="src(page)" />
          <img v-if="secondPage" :src="src(page + 1)" />
        </v-card>
      </v-window-item>
    </v-window>
  </div>
</template>

<script>
import { mapGetters, mapState } from "pinia";
const VuePdfEmbed = () => import("vue-pdf-embed/dist/vue2-pdf-embed");

import { getComicPageSource } from "@/api/v3/reader";
import { useReaderStore } from "@/stores/reader";

//const PLACEHOLDER_ENGAGE_MS = 500;
const TOOLBAR_HEIGHT = 48;

export default {
  name: "ReaderWindow",
  components: { VuePdfEmbed },
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
      secondPage: (state) =>
        state.settings.twoPages && this.currentPage + 1 <= state.comic.maxPage,
    }),
    ...mapGetters(useReaderStore, ["computedSettings"]),
    displayPage() {
      return this.currentPage <= this.maxPage && this.currentPage >= 0;
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
      return getComicPageSource(routeParams, this.timestamp);
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
    change(page) {
      console.log({ page });
      const params = {
        ...this.$router.currentRoute.params,
        page,
      };
      console.log({ params });
      this.$router.push({ params });
    },
    click(event) {
      const columnWidth = window.innerWidth / 3;
      if (
        event.y < TOOLBAR_HEIGHT ||
        event.y > window.innerHeight - TOOLBAR_HEIGHT ||
        (event.x > columnWidth && event.x < window.innerWidth - columnWidth)
      ) {
        this.$emit("click");
      } else {
        if (event.x < columnWidth) {
          if (this.currentPage > 0) {
            console.log("back");
            const page = this.currentPage - 1;
            const params = {
              ...this.$router.currentRoute.params,
              page,
            };

            this.$router.push({ params });
          }
        } else {
          if (this.currentPage < this.maxPage) {
            console.log("forth");
            const page = this.currentPage + 1;
            const params = {
              ...this.$router.currentRoute.params,
              page,
            };

            this.$router.push({ params });
          }
        }
      }
    },
  },
};
</script>

<style scoped lang="scss">
/*
#window,
 #window .v-window__item {
  height: 100% !important;
}
*/
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

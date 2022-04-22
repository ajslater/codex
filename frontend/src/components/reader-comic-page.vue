<template>
  <div v-if="displayPage" :id="page">
    <vue-pdf-embed
      v-if="isPDF"
      :source="src"
      :page="1"
      :width="pdfWidth"
      :height="pdfHeight"
    />
    <img v-else :class="fitToClass" :src="src" :alt="alt" />
  </div>
</template>

<script>
import VuePdfEmbed from "vue-pdf-embed/dist/vue2-pdf-embed";
import { mapGetters, mapState } from "vuex";

import { getComicPageSource } from "@/api/v2/comic";

export default {
  name: "ReaderComicPage",
  components: { VuePdfEmbed },
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
      const fitTo = this.computedSettings.fitTo;
      console.log(fitTo);
      let width = 0;
      if (fitTo === "WIDTH") {
        width = window.innerWidth;
      }
      if (width && this.computedSettings.twoPages) {
        width = width / 2;
      }
      return width;
    },
    pdfHeight() {
      const fitTo = this.computedSettings.fitTo;
      console.log(fitTo);
      if (fitTo == "HEIGHT") {
        return window.innerHeight;
      }
      return 0;
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

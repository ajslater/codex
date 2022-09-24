<template>
  <v-window
    id="pageWindow"
    ref="pageWindow"
    v-model="windowPage"
    show-arrows
    @change="change"
  >
    <template #prev="{ on, attrs }">
      <div class="navColumn" v-bind="attrs" v-on="on"></div>
    </template>
    <template #next="{ on, attrs }">
      <div class="navColumn" v-bind="attrs" v-on="on"></div>
    </template>
    <v-window-item
      v-for="(_, page) in maxPage + 1"
      :key="`${pk}${page}`"
      class="windowItem"
    >
      <PDFPage v-if="isPDF" :source="getSrc(page)" />
      <img
        v-else
        class="page"
        :src="getSrc(page)"
        :class="fitToClass"
        :alt="`Page ${page}`"
      />
      <PDFPage
        v-if="secondPage && isPDF"
        :source="getSrc(page + 1)"
        :classes="fitToClass"
      />
      <img
        v-else-if="secondPage"
        class="page"
        :src="getSrc(page + 1)"
        :alt="`Page ${page + 1}`"
      />
    </v-window-item>
  </v-window>
</template>

<script>
import { mapActions, mapGetters, mapState, mapWritableState } from "pinia";

import { getComicPageSource } from "@/api/v3/reader";
const PDFPage = () => import("@/components/reader/pdf.vue");
import { useReaderStore } from "@/stores/reader";

export default {
  name: "ReaderWindow",
  components: {
    PDFPage,
  },
  data() {
    return {
      windowPage: 0,
    };
  },
  head() {
    if (this.prefetchHref) {
      return {
        lnk: [{ rel: "prefetch", as: "image", href: this.prefetchHref }],
      };
    }
  },
  computed: {
    ...mapState(useReaderStore, {
      maxPage: (state) => state.comic.maxPage || 0,
      nextRoute: (state) => state.routes.next,
      timestamp: (state) => state.timestamp,
      secondPage(state) {
        return (
          state.computedSettings.twoPages &&
          +this.windowPage + 1 <= state.comic.maxPage
        );
      },
      isPDF: (state) => state.comic.fileFormat === "pdf",
      routes: (state) => state.routes,
    }),
    ...mapWritableState(useReaderStore, ["bookChange"]),
    ...mapGetters(useReaderStore, ["computedSettings", "fitToClass"]),
    prefetchHref() {
      if (!this.nextRoute) {
        return;
      }
      return getComicPageSource(this.nextRoute, this.timestamp);
    },
    pk() {
      return this.$route.params.pk;
    },
  },
  watch: {
    $route: function () {
      this.setPage();
    },
  },
  created() {
    this.setPage();
  },
  mounted() {
    const windowContainer = this.$refs.pageWindow.$el.children[0];
    windowContainer.addEventListener("click", this.click);
  },
  unmounted() {
    const windowContainer = this.$refs.pageWindow.$el.children[0];
    windowContainer.removeEventListener("click", this.click);
  },
  methods: {
    ...mapActions(useReaderStore, ["routeToPage"]),
    getSrc(page) {
      const routeParams = { ...this.$router.currentRoute.params, page };
      return getComicPageSource(routeParams, this.timestamp);
    },
    setPage: function () {
      this.windowPage = +this.$router.currentRoute.params.page;
    },
    change(page) {
      this.routeToPage(page);
    },
    click(event) {
      const navColumnWidth = window.innerWidth / 3;
      if (this.routes.prevBook && event.x < navColumnWidth) {
        this.bookChange = "prev";
      } else if (
        this.routes.nextBook &&
        event.x > window.innerWidth - navColumnWidth
      ) {
        this.bookChange = "next";
      } else {
        this.bookChange = undefined;
        this.$emit("click");
      }
    },
  },
};
</script>

<style scoped lang="scss">
.navColumn {
  width: 100%;
  height: 100%;
}
.windowItem {
  /* keeps clickable area full screen when image is small */
  min-height: 100vh;
  text-align: center;
}
.fitToScreen,
.fitToScreenTwo {
  max-height: 100vh;
}
.fitToScreen {
  max-width: 100vw;
}
.fitToHeight,
.fitToHeightTwo {
  height: 100vh;
}
.fitToWidth {
  width: 100vw;
}
.fitToWidthTwo {
  width: 50vw;
}
.fitToScreenTwo {
  max-width: 50vw;
}
.fitToOrig,
.fitToOrigTwo {
  object-fit: none;
}
</style>
<!-- eslint-disable-next-line vue-scoped-css/enforce-style-type -->
<style lang="scss">
#pageWindow .v-window__prev,
#pageWindow .v-window__next {
  top: 48px;
  width: 33vw;
  height: calc(100vh - 96px);
  opacity: 0.2;
}
#pageWindow .v-window__prev {
  cursor: w-resize;
}
#pageWindow .v-window__next {
  cursor: e-resize;
}
</style>

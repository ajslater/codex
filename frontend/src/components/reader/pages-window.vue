<template>
  <v-window
    id="pagesWindow"
    ref="pagesWindow"
    show-arrows
    :value="windowPage"
    :vertical="vertical"
  >
    <div
      id="bookChangePrev"
      class="bookChangeColumn"
      :class="{ upArrow: routes.prevBook }"
      @click.stop="bookChange('prev')"
    />
    <div
      id="bookChangeNext"
      class="bookChangeColumn"
      :class="{ downArrow: routes.nextBook }"
      @click.stop="bookChange('next')"
    />
    <template #prev>
      <div
        class="pageChangeColumn"
        aria-label="previous page"
        @click.stop="pageChange('prev')"
      />
    </template>
    <template #next>
      <div
        class="pageChangeColumn"
        aria-label="next page"
        @click.stop="pageChange('next')"
      />
    </template>
    <v-window-item
      v-for="(_, page) in numWindowItems"
      :key="`c/${pk}/${page}`"
      class="windowItem"
      disabled
      :eager="page >= windowPage - 1 && page <= windowPage + 2"
    >
      <PDFPage v-if="isPDF" :source="getSrc(page)" />
      <img
        v-else
        class="page"
        :class="fitToClass"
        :src="getSrc(page)"
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
        :class="fitToClass"
        :src="getSrc(page + 1)"
        :alt="`Page ${page + 1}`"
      />
    </v-window-item>
  </v-window>
</template>

<script>
import { mapActions, mapGetters, mapState } from "pinia";

import { getComicPageSource } from "@/api/v3/reader";
const PDFPage = () => import("@/components/reader/pdf.vue");
import { useReaderStore } from "@/stores/reader";

const PREFETCH_LINK = { rel: "prefetch", as: "image" };

export default {
  name: "PagesWindow",
  components: {
    PDFPage,
  },
  data() {
    return {
      windowPage: 0,
    };
  },
  head() {
    const links = [];
    if (this.nextSrc) {
      links.push({ ...PREFETCH_LINK, href: this.nextSrc });
    }
    if (this.prevSrc) {
      links.push({ ...PREFETCH_LINK, href: this.prevSrc });
    }
    if (links.length > 0) {
      return { link: links };
    }
  },
  computed: {
    ...mapGetters(useReaderStore, ["computedSettings", "fitToClass"]),
    ...mapState(useReaderStore, {
      numWindowItems: (state) => {
        if (state.comic) {
          return (state.comic.maxPage || 0) + 1;
        }
        return 0;
      },
      isPDF: (state) =>
        state.comic ? state.comic.fileFormat === "pdf" : false,
      routes: (state) => state.routes,
      timestamp: (state) => state.timestamp,
      secondPage(state) {
        return (
          state.computedSettings.twoPages &&
          +this.windowPage + 1 <= state.comic.maxPage
        );
      },
      vertical: (state) => state.bookChange !== undefined,
      nextSrc(state) {
        const routes = state.routes;
        let route;
        if (routes.next) {
          route = routes.next;
        } else if (routes.nextBook) {
          route = routes.nextBook;
        }
        if (route) {
          return getComicPageSource(route, state.timestamp);
        }
      },
      prevSrc(state) {
        const routes = state.routes;
        let route;
        if (routes.prev) {
          route = routes.prev;
        } else if (routes.prevBook) {
          route = routes.prevBook;
        }
        if (route) {
          return getComicPageSource(route, state.timestamp);
        }
      },
      comicLoaded: (state) => state.comicLoaded,
    }),
    pk() {
      return this.$route.params.pk;
    },
  },
  watch: {
    $route(to, from) {
      if (!from || !from.params || +to.params.pk !== +from.params.pk) {
        this.loadBook();
      } else {
        this.setRoutesAndBookmarkPage();
        this.setPage(+to.params.page);
      }
    },
    comicLoaded() {
      this.setPage();
    },
  },
  mounted() {
    const windowContainer = this.$refs.pagesWindow.$el.children[0];
    windowContainer.addEventListener("click", this.click);
  },
  unmounted() {
    const windowContainer = this.$refs.pagesWindow.$el.children[0];
    windowContainer.removeEventListener("click", this.click);
  },
  methods: {
    ...mapActions(useReaderStore, [
      "loadBook",
      "routeToDirection",
      "setBookChangeFlag",
      "setRoutesAndBookmarkPage",
    ]),
    getSrc(page) {
      const routeParams = { ...this.$route.params, page };
      return getComicPageSource(routeParams, this.timestamp);
    },
    setPage(page) {
      if (!this.comicLoaded) {
        return;
      }
      if (page === undefined) {
        page = +this.$route.params.page || 0;
      }
      this.windowPage = page;
      window.scrollTo(0, 0);
    },
    pageChange(direction) {
      this.routeToDirection(direction);
    },
    bookChange(direction) {
      if (this.routes[direction + "Book"]) {
        this.setBookChangeFlag(direction);
      } else {
        this.click();
      }
    },
    click() {
      this.setBookChangeFlag();
      this.$emit("click");
    },
  },
};
</script>

<style scoped lang="scss">
.pageChangeColumn {
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
.bookChangeColumn {
  position: fixed;
  top: 48px;
  width: 33vw;
  height: calc(100vh - 96px);
  z-index: 5;
}
#bookChangePrev {
  left: 0px;
}
.upArrow {
  cursor: n-resize;
}
#bookChangeNext {
  right: 0px;
}
.downArrow {
  cursor: s-resize;
}
</style>
<!-- eslint-disable-next-line vue-scoped-css/enforce-style-type -->
<style lang="scss">
#pagesWindow .v-window__prev,
#pagesWindow .v-window__next {
  position: fixed;
  top: 48px;
  width: 33vw;
  height: calc(100vh - 96px);
  border-radius: 0;
  opacity: 0;
  z-index: 10;
}
#pagesWindow .v-window__prev {
  cursor: w-resize;
}
#pagesWindow .v-window__next {
  cursor: e-resize;
}
</style>

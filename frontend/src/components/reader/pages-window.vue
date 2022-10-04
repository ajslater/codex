<template>
  <v-window id="pagesWindow" ref="pagesWindow" show-arrows :value="activePage">
    <div
      id="bookChangeActivatorPrev"
      class="bookChangeActivatorColumn"
      :class="{ upArrow: series.prev }"
      @click.stop="setBookChange('prev')"
    />
    <div
      id="bookChangeActivatorNext"
      class="bookChangeActivatorColumn"
      :class="{ downArrow: series.next }"
      @click.stop="setBookChange('next')"
    />
    <template #prev>
      <PageChangeLink direction="prev" />
    </template>
    <template #next>
      <PageChangeLink direction="next" />
    </template>
    <v-window-item
      v-for="page of pages"
      :key="`c/${pk}/${page}`"
      class="windowItem"
      disabled
      :eager="page >= activePage - 1 && page <= activePage + 2"
    >
      <PDFPage v-if="isPDF" :pk="pk" :page="page" />
      <ComicPage v-else :pk="pk" :page="page" />
      <PDFPage v-if="secondPage && isPDF" :pk="pk" :page="page + 1" />
      <ComicPage v-else-if="secondPage" :pk="pk" :page="page + 1" />
    </v-window-item>
  </v-window>
</template>

<script>
import { mapActions, mapGetters, mapState } from "pinia";

const PDFPage = () => import("@/components/reader/pdf.vue");
import _ from "lodash";

import PageChangeLink from "@/components/reader/change-page-link.vue";
import ComicPage from "@/components/reader/page.vue";
import { useReaderStore } from "@/stores/reader";
export default {
  name: "PagesWindow",
  components: {
    PDFPage,
    ComicPage,
    PageChangeLink,
  },
  props: {
    pk: { type: Number, required: true },
  },
  data() {
    return {
      activePage: undefined,
    };
  },
  computed: {
    ...mapGetters(useReaderStore, ["computedSettings"]),
    ...mapState(useReaderStore, {
      pages(state) {
        const len = state.comic ? state.comic.maxPage + 1 : 0;
        return _.range(len);
      },
      maxPage: (state) => state.comic.maxPage || 0,
      isPDF: (state) =>
        state.comic ? state.comic.fileFormat === "pdf" : false,
      secondPage(state) {
        return (
          state.computedSettings.twoPages &&
          +this.activePage + 1 <= state.comic.maxPage
        );
      },
      comicLoaded: (state) => state.comicLoaded,
      bookChange: (state) => state.bookChange,
      comicPk: (state) => state.comic.pk,
      series: (state) => state.comic.series,
    }),
  },
  watch: {
    $route(to) {
      if (+to.params.pk === this.pk && this.comicLoaded) {
        this.setRoutesAndBookmarkPage();
        this.setActivePage();
      }
    },
    comicLoaded(to) {
      if (to) {
        this.setActivePage();
      }
    },
  },
  created() {
    if (this.pk === +this.$route.params.pk) {
      this.activePage = +this.$route.params.page;
    } else if (this.bookChange === "prev") {
      // XXX this.bookChange seems a little hacky
      this.activePage = +this.series.prev.page;
    } else {
      this.activePage = 0;
    }
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
      "routeToPage",
      "setBookChangeFlag",
      "setRoutesAndBookmarkPage",
    ]),
    setActivePage() {
      if (
        !this.comicLoaded ||
        this.pk !== +this.$route.params.pk ||
        this.pk !== this.comicPk
      ) {
        return;
      }
      const page = +this.$route.params.page || 0;
      if (page < 0) {
        console.warn("Page out of bounds. Redirecting to 0.");
        return this.routeToPage(0);
      }
      if (page > this.maxPage) {
        console.warn(`Page out of bounds. Redirecting to ${this.maxPage}.`);
        return this.routeToPage(this.maxPage);
      }
      this.activePage = page;
      window.scrollTo(0, 0);
    },
    setBookChange(direction) {
      if (this.series[direction]) {
        this.setBookChangeFlag(direction);
      }
    },
  },
};
</script>

<style scoped lang="scss">
.windowItem {
  /* keeps clickable area full screen when image is small */
  min-height: 100vh;
  text-align: center;
}
.bookChangeActivatorColumn {
  position: fixed;
  top: 48px;
  width: 33vw;
  height: calc(100vh - 96px);
  z-index: 5;
}
#bookChangeActivatorPrev {
  left: 0px;
}
.upArrow {
  cursor: n-resize;
}
#bookChangeActivatorNext {
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
</style>

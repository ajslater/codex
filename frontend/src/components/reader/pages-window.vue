<template>
  <v-window id="pagesWindow" ref="pagesWindow" show-arrows :value="activePage">
    <div
      id="bookChangeActivatorPrev"
      class="bookChangeActivatorColumn"
      :class="{ upArrow: bookExists('prev') }"
      @click.stop="setBookChange('prev')"
    />
    <div
      id="bookChangeActivatorNext"
      class="bookChangeActivatorColumn"
      :class="{ downArrow: bookExists('next') }"
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
      :key="`c/${book.pk}/${page}`"
      class="windowItem"
      disabled
      :eager="page >= activePage - 1 && page <= activePage + 2"
      :value="page"
    >
      <BookPage
        :book="book"
        :settings="settings"
        :fit-to-class="fitToClass"
        :page="page"
      />
      <BookPage
        v-if="secondPage"
        :book="book"
        :settings="settings"
        :fit-to-class="fitToClass"
        :page="page + 1"
      />
    </v-window-item>
  </v-window>
</template>

<script>
import _ from "lodash";
import { mapActions, mapState } from "pinia";

import PageChangeLink from "@/components/reader/change-page-link.vue";
import BookPage from "@/components/reader/page.vue";
import { useReaderStore } from "@/stores/reader";

export default {
  name: "PagesWindow",
  components: {
    BookPage,
    PageChangeLink,
  },
  props: {
    book: { type: Object, required: true },
  },
  emits: ["click"],
  data() {
    return {
      activePage: undefined,
    };
  },
  computed: {
    ...mapState(useReaderStore, {
      bookRoutes: (state) => state.routes.books,
      settings(state) {
        const bookSettings = state.books.get(this.book.pk).settings;
        return state.getSettings(state.readerSettings, bookSettings);
      },
      prevBookPk: (state) => state.routes.books?.prev.pk,
      twoPages: (state) => state.activeSettings.twoPages,
    }),
    fitToClass() {
      return this.getFitToClass(this.settings);
    },
    pages() {
      const len = this.book?.maxPage + 1 ?? 0;
      const step = this.settings.twoPages ? 2 : 1;
      return _.range(0, len, step);
    },
    secondPage() {
      return (
        this.settings.twoPages && +this.activePage + 1 <= this.book.maxPage
      );
    },
  },
  watch: {
    $route(to) {
      if (+to.params.pk === this.book.pk) {
        this.setActivePageForRoute(+to.params.page);
      }
    },
    twoPages() {
      this.setActivePageForRoute(+this.$route.params.page);
    },
  },
  created() {
    let page;
    if (this.book.pk === +this.$route.params.pk) {
      // Active Book
      page = +this.$route.params.page;
    } else if (this.book.pk === this.prevBookPk) {
      // Prev Book
      page = this.book.maxPage;
    } else {
      // Must be next book
      page = 0;
    }
    this.activePage = page;
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
      "routeToPage",
      "setBookChangeFlag",
      "setRoutesAndBookmarkPage",
      "setRoutes",
      "getSettings",
      "getFitToClass",
    ]),
    setActivePageForRoute(page) {
      if (page < 0) {
        console.warn("Page out of bounds. Redirecting to 0.");
        return this.routeToPage(0);
      } else if (page > this.book.maxPage) {
        console.warn(
          `Page out of bounds. Redirecting to ${this.book.maxPage}.`
        );
        return this.routeToPage(this.book.maxPage);
      } else if (this.settings.twoPages && page % 2 !== 0) {
        console.debug(
          `Requested odd page ${page} in two pages mode. Flip back one`
        );
        return this.routeToPage(page - 1);
      }
      this.activePage = page;
      this.setRoutesAndBookmarkPage(+this.$route.params.page);
      window.scrollTo(0, 0);
    },
    setBookChange(direction) {
      if (this.bookRoutes[direction]) {
        this.setBookChangeFlag(direction);
      } else {
        this.$emit("click");
      }
    },
    bookExists(direction) {
      return Boolean(this.bookRoutes[direction]);
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

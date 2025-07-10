<template>
  <v-window
    show-arrows
    continuous
    :model-value="windowIndex"
    :reverse="isReadInReverse"
  >
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
      :eager="page >= storePage - 1 && page <= storePage + 2"
      :model-value="page"
      :transition="transition"
      :reverse-transition="transition"
    >
      <HorizontalPages :book="book" :page="page" />
    </v-window-item>
  </v-window>
</template>

<script>
import { mapActions, mapState } from "pinia";

import HorizontalPages from "@/components/reader/pager/horizontal-pages.vue";
import PageChangeLink from "@/components/reader/pager/page-change-link.vue";
import { useReaderStore } from "@/stores/reader";
import { range } from "@/util";

const WINDOW_BACK_BOUND = 48;
const WINDOW_FORE_BOUND = 48;

export default {
  name: "PagerHorizontal",
  components: {
    HorizontalPages,
    PageChangeLink,
  },
  props: {
    book: { type: Object, required: true },
  },
  data() {
    return {
      activePage: 0,
      pages: [],
    };
  },
  computed: {
    ...mapState(useReaderStore, {
      prevBook: (state) => state.routes.books?.prev,
      nextBook: (state) => state.routes.books?.next,
      storePage: (state) => state.page,
      storePk: (state) => state.books.current.pk,
      transition: (state) => state.readerSettings.pageTransition,
    }),
    bookSettings() {
      return this.getBookSettings(this.book);
    },
    twoPages() {
      return this.bookSettings.twoPages;
    },
    isReadInReverse() {
      return this.bookSettings.isReadInReverse;
    },
    windowIndex() {
      const val = this.activePage - this.pages[0];
      return Math.min(Math.max(0, val), this.book.maxPage);
    },
  },
  watch: {
    twoPages() {
      this.setActivePage(this.storePage, true);
    },
    storePage(to) {
      if (this.book.pk === this.storePk) {
        this.activePage = to;
        const backLimit = this.pages.at(0);
        const foreLimit = this.pages.at(-1);
        if (to < backLimit || to > foreLimit) {
          this.setPages();
        }
      }
    },
  },
  created() {
    if (this.book.pk === this.storePk) {
      // Active Book
      this.activePage = +this.$route.params.page;
    } else if (this.book.pk === this.prevBook.pk) {
      // Prev Book
      this.activePage = this.book.maxPage;
    } else {
      // Must be next book
      this.activePage = 0;
    }
    this.setPages();
  },
  methods: {
    ...mapActions(useReaderStore, [
      "getBookSettings",
      "setBookChangeFlag",
      "setActivePage",
    ]),
    setPages() {
      const backPages = Math.max(this.activePage - WINDOW_BACK_BOUND, 0);
      const forePages = Math.min(
        this.activePage + WINDOW_FORE_BOUND,
        this.book.maxPage,
      );
      this.pages = range(backPages, forePages + 1);
    },
  },
};
</script>

/* Inherits v-window styles from books-window */
<style scoped lang="scss">
.windowItem {
  /* prevents inline images from padding and producing scroll bars */
  font-size: 0;
}
</style>

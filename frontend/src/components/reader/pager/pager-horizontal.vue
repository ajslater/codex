<template>
  <v-window continuous :model-value="windowIndex" :reverse="isReadInReverse">
    <v-window-item
      v-for="page of pages"
      :key="`c/${book.pk}/${page}`"
      class="windowItem"
      disabled
      :eager="page >= storePage - 1 && page <= storePage + 2"
      :model-value="page"
      :transition="true"
    >
      <HorizontalPages
        :book="book"
        :page="page"
        :is-read-in-reverse="isReadInReverse"
      />
    </v-window-item>
  </v-window>
</template>

<script>
import { mapActions, mapState } from "pinia";

import HorizontalPages from "@/components/reader/pager/horizontal-pages.vue";
import { REVERSE_READING_DIRECTIONS, useReaderStore } from "@/stores/reader";
import { range } from "@/util";

const WINDOW_BACK_BOUND = 48;
const WINDOW_FORE_BOUND = 48;

export default {
  name: "PagerHorizontal",
  components: {
    HorizontalPages,
  },
  props: {
    book: { type: Object, required: true },
    bookSettings: { type: Object, required: true },
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
    }),
    twoPages() {
      return this.bookSettings.twoPages;
    },
    isReadInReverse() {
      return REVERSE_READING_DIRECTIONS.has(this.bookSettings.readingDirection);
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
    prevBook(to) {
      if (this.book.pk === to.pk) {
        this.activePage = this.book.maxPage;
      }
    },
    nextBook(to) {
      if (this.book.pk === to.pk) {
        this.activePage = 0;
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
    ...mapActions(useReaderStore, ["setBookChangeFlag", "setActivePage"]),
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

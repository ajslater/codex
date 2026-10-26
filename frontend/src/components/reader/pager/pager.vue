<template>
  <!--
    ``:key="component.name"`` forces a full unmount + remount
    when the user toggles reading direction. Without it Vue
    reuses the existing pager instance — the orientation swap
    keeps the previous mode's scroll listeners attached and the
    new mode's setup runs against stale state. Keying on the
    component identity scopes lifecycle correctly.
  -->
  <component :is="component" :key="component.name" :book="book" />
</template>

<script>
import { mapActions, mapState } from "pinia";

import PagerHorizontal from "@/components/reader/pager/pager-horizontal.vue";
import PagerVertical from "@/components/reader/pager/pager-vertical.vue";
import { useReaderStore } from "@/stores/reader";

export default {
  name: "PagerSelector",
  components: {
    PagerHorizontal,
    PagerVertical,
  },
  props: {
    book: { type: Object, required: true },
  },
  emits: ["click"],
  head() {
    return this.prefetchBook(this.book);
  },
  computed: {
    ...mapState(useReaderStore, {
      storePk: (state) => state.books?.current?.pk || 0,
    }),
    isActiveBook() {
      return this.book && this.storePk === this.book?.pk;
    },
    bookSettings() {
      return this.getBookSettings(this.book);
    },
    component() {
      /*
       * PDF books now render page-by-page (image-first with
       * PDFDoc fallback handled inside ``BookPage``), so the
       * orientation alone decides the pager.
       */
      return this.bookSettings.isVertical ? PagerVertical : PagerHorizontal;
    },
  },
  watch: {
    /*
     * ``setActivePage`` acts on the store's current book. On a book change
     * the route moves before ``loadBooks`` swaps the books, so a pager the
     * book-change flag already mounted must wait until its book is current,
     * or it pages and bookmarks the book being left.
     */
    $route(to) {
      if (this.isActiveBook && +to.params.pk === this.book.pk) {
        this.setActivePage(Number(to.query.page) || 0, true);
      }
    },
    isActiveBook: {
      handler(isActive) {
        if (isActive) {
          this.setActivePage(Number(this.$route.query.page) || 0, true);
        }
      },
      immediate: true,
    },
  },
  methods: {
    ...mapActions(useReaderStore, [
      "getBookSettings",
      "setActivePage",
      "prefetchBook",
    ]),
  },
};
</script>

/* Inherits v-window styles from books-window */

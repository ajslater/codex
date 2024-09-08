<template>
  <component
    :is="component"
    :book="book"
    :book-settings="bookSettings"
    :is-vertical="isVertical"
  />
</template>

<script>
import { mapActions, mapState } from "pinia";
import { defineAsyncComponent, markRaw } from "vue";

import PagerHorizontal from "@/components/reader/pager/pager-horizontal.vue";
const PagerPDF = markRaw(
  defineAsyncComponent(() => "@/components/reader/pager/pager-full-pdf.vue"),
);
import PagerVertical from "@/components/reader/pager/pager-vertical.vue";
import { useReaderStore, VERTICAL_READING_DIRECTIONS } from "@/stores/reader";

export default {
  name: "PagerSelector",
  components: {
    PagerHorizontal,
    PagerPDF,
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
      return this.getSettings(this.book);
    },
    isVertical() {
      return VERTICAL_READING_DIRECTIONS.has(
        this.bookSettings.readingDirection,
      );
    },
    readerFullPdf() {
      return (
        this.book?.fileType == "PDF" &&
        this.bookSettings.cacheBook &&
        !this.isVertical
      );
    },
    component() {
      if (this.readerFullPdf) {
        return PagerPDF;
      } else if (this.isVertical) {
        return PagerVertical;
      } else {
        return PagerHorizontal;
      }
    },
  },
  watch: {
    $route(to) {
      if (+to.params.pk === this.book.pk) {
        this.setActivePage(+to.params.page, true);
      }
    },
  },
  created() {
    if (this.isActiveBook) {
      // Active Book
      this.setActivePage(+this.$route.params.page, true);
    }
  },
  methods: {
    ...mapActions(useReaderStore, [
      "getSettings",
      "setActivePage",
      "prefetchBook",
    ]),
  },
};
</script>

/* Inherits v-window styles from books-window */

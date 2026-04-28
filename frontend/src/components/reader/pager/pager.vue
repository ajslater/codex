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
import { defineAsyncComponent, markRaw } from "vue";

import PagerHorizontal from "@/components/reader/pager/pager-horizontal.vue";
const PagerPDF = markRaw(
  defineAsyncComponent(
    () => import("@/components/reader/pager/pager-full-pdf.vue"),
  ),
);
import PagerVertical from "@/components/reader/pager/pager-vertical.vue";
import { useReaderStore } from "@/stores/reader";

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
    ...mapState(useReaderStore, ["cacheBook"]),
    ...mapState(useReaderStore, {
      storePk: (state) => state.books?.current?.pk || 0,
    }),
    isActiveBook() {
      return this.book && this.storePk === this.book?.pk;
    },
    bookSettings() {
      return this.getBookSettings(this.book);
    },
    readerFullPdf() {
      return (
        this.book?.fileType == "PDF" &&
        this.cacheBook &&
        !this.bookSettings.isVertical
      );
    },
    component() {
      let comp;
      if (this.readerFullPdf) {
        comp = PagerPDF;
      } else if (this.bookSettings.isVertical) {
        comp = PagerVertical;
      } else {
        comp = PagerHorizontal;
      }
      return comp;
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
      "getBookSettings",
      "isBookVertical",
      "setActivePage",
      "prefetchBook",
    ]),
  },
};
</script>

/* Inherits v-window styles from books-window */

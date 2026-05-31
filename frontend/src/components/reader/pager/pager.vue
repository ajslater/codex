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
    $route(to) {
      if (+to.params.pk === this.book.pk) {
        this.setActivePage(Number(to.query.page) || 0, true);
      }
    },
  },
  created() {
    if (this.isActiveBook) {
      // Active Book
      this.setActivePage(Number(this.$route.query.page) || 0, true);
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

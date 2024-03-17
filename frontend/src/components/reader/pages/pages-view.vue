<template>
  <PagesPdf v-if="readFullPdf" :book="book" />
  <PagesVerticalScroller v-else-if="isVertical" :book="book" />
  <PagesHorizontalWindow v-else :book="book" />
</template>

<script>
import { mapActions, mapGetters, mapState } from "pinia";

import PagesPdf from "@/components/reader/pages/full-pdf.vue";
import PagesHorizontalWindow from "@/components/reader/pages/horizontal-window.vue";
import PagesVerticalScroller from "@/components/reader/pages/vertical-scroller.vue";
import { useReaderStore } from "@/stores/reader";

export default {
  name: "PagesView",
  components: {
    PagesHorizontalWindow,
    PagesPdf,
    PagesVerticalScroller,
  },
  props: {
    book: { type: Object, required: true },
  },
  emits: ["click"],
  head() {
    return this.prefetchBook(this.book);
  },
  computed: {
    ...mapGetters(useReaderStore, ["isVertical", "cacheBook"]),
    ...mapState(useReaderStore, {
      storePk: (state) => state.books?.current?.pk || 0,
    }),
    readFullPdf() {
      return this.book.fileType == "PDF" && this.cacheBook;
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
    if (this.book.pk === this.storePk) {
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

<template>
  <PagerPDF v-if="readFullPdf" :book="book" />
  <PagerVerticalScroller v-else-if="isVertical" :book="book" />
  <PagerHorizontalWindow v-else :book="book" />
</template>

<script>
import { mapActions, mapGetters, mapState } from "pinia";
import { defineAsyncComponent, markRaw } from "vue";
const PagerPDF = markRaw(
  defineAsyncComponent(() => "@/components/reader/pager/pager-full-pdf.vue"),
);
import PagerHorizontalWindow from "@/components/reader/pager/pager-horizontal.vue";
import PagerVerticalScroller from "@/components/reader/pager/pager-vertical.vue";
import { useReaderStore } from "@/stores/reader";

export default {
  name: "PagerSelector",
  components: {
    PagerHorizontalWindow,
    PagerPDF,
    PagerVerticalScroller,
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

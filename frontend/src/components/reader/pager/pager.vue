<template>
  <component :is="component" :book="book" />
</template>

<script>
import { mapActions, mapGetters, mapState } from "pinia";
import { defineAsyncComponent, markRaw } from "vue";
const PagerPDF = markRaw(
  defineAsyncComponent(() => "@/components/reader/pager/pager-full-pdf.vue"),
);
import PagerHorizontal from "@/components/reader/pager/pager-horizontal.vue";
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
    ...mapGetters(useReaderStore, ["isVertical", "cacheBook"]),
    ...mapState(useReaderStore, {
      storePk: (state) => state.books?.current?.pk || 0,
    }),
    readFullPdf() {
      return this.book.fileType == "PDF" && this.cacheBook;
    },
    component() {
      let comp;
      if (this.readFullPdf) {
        comp = PagerPDF;
      } else if (this.isVertical) {
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

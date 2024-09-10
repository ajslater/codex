<template>
  <span>
    <PageChangeLink direction="prev" :is-vertical="isVertical" />
    <PageChangeLink direction="next" :is-vertical="isVertical" />
    <ScaleForScroll>
      <PDFDoc
        :book="book"
        :book-settings="bookSettings"
        :is-vertical="isVertical"
        :page="page"
        :src="src"
      />
    </ScaleForScroll>
  </span>
</template>

<script>
import { mapState } from "pinia";

import { getPDFInBrowserURL } from "@/api/v3/reader";
import PageChangeLink from "@/components/reader/pager/page-change-link.vue";
import PDFDoc from "@/components/reader/pager/pdf-doc.vue";
import ScaleForScroll from "@/components/reader/pager/scale-for-scroll.vue";
import { useReaderStore } from "@/stores/reader";

export default {
  name: "PagerFullPDF",
  components: { PageChangeLink, PDFDoc, ScaleForScroll },
  props: {
    book: { type: Object, required: true },
    bookSettings: { type: Object, required: true },
    isVertical: { type: Boolean, required: true },
  },
  emits: ["load", "error", "unauthorized"],
  computed: {
    ...mapState(useReaderStore, {
      page: (state) => state.page || 0,
    }),
    src() {
      return getPDFInBrowserURL(this.book);
    },
  },
};
</script>

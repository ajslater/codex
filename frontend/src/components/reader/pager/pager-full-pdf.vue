<template>
  <span>
    <PageChangeLink direction="prev" />
    <PageChangeLink direction="next" />
    <ScaleForScroll>
      <PDFDoc :book="book" :page="page" :src="src" />
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

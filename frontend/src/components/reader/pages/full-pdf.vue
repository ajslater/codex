<template>
  <span>
    <PageChangeLink direction="prev" />
    <PageChangeLink direction="next" />
    <PdfDoc :book="book" :fit-to-class="fitToClass" :page="page" :src="src" />
  </span>
</template>

<script>
import { mapState } from "pinia";

import { getPdfBookSource } from "@/api/v3/reader";
import PdfDoc from "@/components/reader/pages/page/pdf.vue";
import PageChangeLink from "@/components/reader/pages/page-change-link.vue";
import { useReaderStore } from "@/stores/reader";

export default {
  name: "PDFPages",
  components: { PageChangeLink, PdfDoc },
  props: {
    book: { type: Object, required: true },
    fitToClass: {
      type: Object,
      required: true,
    },
  },
  emits: ["load", "error", "unauthorized"],
  computed: {
    ...mapState(useReaderStore, {
      page: (state) => state.page,
    }),
    src() {
      return getPdfBookSource(this.book);
    },
  },
};
</script>

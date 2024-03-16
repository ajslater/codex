<template>
  <span>
    <PageChangeLink direction="prev" />
    <PageChangeLink direction="next" />
    <ScaleForScroll>
      <PdfDoc
        :book="book"
        :fit-to-class="fitToClass"
        :page="page"
        :src="src"
        class="fullPdfPage"
      />
    </ScaleForScroll>
  </span>
</template>

<script>
import { mapState } from "pinia";

import { getPdfBookSource } from "@/api/v3/reader";
import PdfDoc from "@/components/reader/pages/page/pdf.vue";
import PageChangeLink from "@/components/reader/pages/page-change-link.vue";
import ScaleForScroll from "@/components/reader/pages/scale-for-scroll.vue";
import { useReaderStore } from "@/stores/reader";

export default {
  name: "PDFPages",
  components: { PageChangeLink, PdfDoc, ScaleForScroll },
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
<style scoped lang="scss">
.fullPdfPage {
  display: block;
}
</style>

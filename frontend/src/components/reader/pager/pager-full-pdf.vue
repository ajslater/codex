<template>
  <span>
    <ScaleForScroll>
      <PdfDoc :book="book" :page="page" :src="src" class="fullPdfPage" />
    </ScaleForScroll>
  </span>
</template>

<script>
import { mapState } from "pinia";

import { getPdfBookSource } from "@/api/v3/reader";
import PdfDoc from "@/components/reader/pager/pdf-doc.vue";
import ScaleForScroll from "@/components/reader/pager/scale-for-scroll.vue";
import { useReaderStore } from "@/stores/reader";

export default {
  name: "PagerFullPDF",
  components: { PdfDoc, ScaleForScroll },
  props: {
    book: { type: Object, required: true },
    isVertical: { type: Boolean, required: true },
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

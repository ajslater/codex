<template>
  <vue-pdf-embed
    class="pdfDoc"
    image-resources-path="https://unpkg.com/pdfjs-dist/web/images/"
    :class="fitToClass"
    :page="page"
    :source="src"
    :width="width"
    :height="height"
    @rendered="$emit('load')"
    @internal-link-clicked="routeToPage"
    @loading-failed="$emit('error')"
    @rendering-failed="$emit('error')"
    @password-requested="$emit('unauthorized')"
  />
</template>

<script>
import { mapActions, mapState } from "pinia";
import VuePdfEmbed from "vue-pdf-embed";

import { useReaderStore } from "@/stores/reader";

export default {
  name: "PDFDoc",
  components: { VuePdfEmbed },
  props: {
    book: { type: Object, required: true },
    fitToClass: {
      type: Object,
      required: true,
    },
    page: { type: Number, required: true },
    src: { type: String, required: true },
  },
  emits: ["load", "error", "unauthorized"],
  data() {
    return {
      innerHeight: window.innerHeight,
      innerWidth: window.innerWidth,
    };
  },
  computed: {
    ...mapState(useReaderStore, ["isVertical"]),
    settings() {
      return this.getSettings(this.book);
    },
    width() {
      // Wide PDFs will not fit to SCREEN well.
      // vue-pdf-embed internal canvas sizing algorithm makes this difficult.
      // Maybe not impossible but I'm lazy right now.
      let width = ["W"].includes(this.settings.fitTo) ? this.innerWidth : 0;
      if (!this.isVertical && this.settings.twoPages) {
        width = width / 2;
      }
      return width;
    },
    height() {
      let height = ["H", "S"].includes(this.settings.fitTo)
        ? this.innerHeight
        : 0;
      if (this.isVertical) {
        // Hack for janky PDF display with vertical scroller.
        height = height * 0.8;
      }
      return height;
    },
  },
  mounted() {
    window.addEventListener("resize", this.onResize);
  },
  beforeUnmount() {
    window.removeEventListener("resize", this.onResize);
  },
  methods: {
    ...mapActions(useReaderStore, ["getSettings", "routeToPage"]),
    onResize() {
      this.innerHeight = window.innerHeight;
      this.innerWidth = window.innerWidth;
    },
  },
};
</script>

<style scoped lang="scss">
.pdfDoc {
  display: inline-block;
}

/* bugfixes for vue-pdf-embed */
:deep(.vue-pdf-embed.fitToHeightTwo > div > canvas),
:deep(.vue-pdf-embed.fitToScreenTwo > div > canvas) {
  width: inherit !important;
}
:deep(.vue-pdf-embed.fitToScreen > div > canvas),
:deep(.vue-pdf-embed.fitToScreenTwo > div > canvas),
:deep(.vue-pdf-embed.fitToScreenVertical > div > canvas) {
  object-fit: contain;
}
:deep(.vue-pdf-embed.fitToWidthTwo > div > canvas) {
  height: inherit !important;
}
:deep(.vue-pdf-embed.fitToOrigTwo > div > canvas) {
  height: inherit !important;
  width: inherit !important;
}
</style>

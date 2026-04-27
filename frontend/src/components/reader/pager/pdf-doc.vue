<template>
  <vue-pdf-embed
    class="pdfDoc"
    image-resources-path="https://unpkg.com/pdfjs-dist/web/images/"
    :class="classes"
    :page="page"
    :source="src"
    :width="width"
    :height="height"
    @rendered="onLoad"
    @internal-link-clicked="onLinkClicked"
    @loading-failed="onError"
    @rendering-failed="onError"
    @password-requested="onUnauthorized"
    @error="onError"
  />
</template>

<script>
import { mapActions, mapState } from "pinia";
import VuePdfEmbed from "vue-pdf-embed";
import { useWindowSize } from "@vueuse/core";

import { useReaderStore, VERTICAL_READING_DIRECTIONS } from "@/stores/reader";

export default {
  name: "PDFDoc",
  components: { VuePdfEmbed },
  props: {
    book: { type: Object, required: true },
    page: { type: Number, required: true },
    src: { type: String, required: true },
  },
  emits: ["load", "error", "unauthorized"],
  setup() {
    const { width, height } = useWindowSize();
    return { innerWidth: width, innerHeight: height };
  },
  computed: {
    ...mapState(useReaderStore, {
      scale: (state) => state.clientSettings.scale,
    }),
    bookSettings() {
      return this.getBookSettings(this.book);
    },
    isVertical() {
      return VERTICAL_READING_DIRECTIONS.has(
        this.bookSettings.readingDirection,
      );
    },
    width() {
      /*
       * Wide PDFs will not fit to SCREEN well.
       * vue-pdf-embed internal canvas sizing algorithm makes this difficult.
       * Maybe not impossible but I'm lazy right now.
       */
      let width = ["W", "O"].includes(this.bookSettings.fitTo)
        ? this.innerWidth
        : 0;
      if (!this.isVertical && this.bookSettings.twoPages) {
        width = width / 2;
      }
      width = width * this.scale;
      return width;
    },
    height() {
      let height = [undefined, "H", "S"].includes(this.bookSettings.fitTo)
        ? this.innerHeight
        : 0;
      if (this.isVertical) {
        // Hack for janky PDF display with vertical scroller.
        height = height * 0.8;
      }
      height = height * this.scale;
      return height;
    },
    classes() {
      return this.bookSettings.fitToClass;
    },
  },
  methods: {
    ...mapActions(useReaderStore, ["getBookSettings", "routeToPage"]),
    onLoad() {
      this.$emit("load");
    },
    onLinkClicked(event) {
      this.routeToPage(event);
    },
    onError(event) {
      console.error(event);
      this.$emit("error");
    },
    onUnauthorized() {
      this.$emit("unauthorized");
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

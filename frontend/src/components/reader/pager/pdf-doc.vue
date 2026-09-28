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
       * vue-pdf-embed sizes by height when width is 0, so Fit to
       * Screen passes only a height and the CSS caps wide pages.
       */
      let width = ["W", "O"].includes(this.bookSettings.fitTo)
        ? this.innerWidth
        : 0;
      if (!this.isVertical && this.bookSettings?.twoPages) {
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
/* Layered: these rules beat Vuetify's component CSS by position,
 * and lose to a `color`/utility prop, which is the intended order. */
@layer codex-components {
  .pdfDoc {
    display: inline-block;
  }

  /*
   * Fit to Screen sizes the canvas by height, so a wide page can be
   * wider than the screen. Cap the width and letterbox the page, as
   * page-img.vue does for images. The embed is this component's root,
   * so these rules scope on it rather than on a top-level :deep().
   */
  .pdfDoc.fitToScreen :deep(canvas),
  .pdfDoc.fitToScreenVertical :deep(canvas) {
    max-width: 100vw;
    object-fit: contain;
  }

  .pdfDoc.fitToScreenTwo :deep(canvas) {
    max-width: 50vw;
    object-fit: contain;
  }
}
</style>

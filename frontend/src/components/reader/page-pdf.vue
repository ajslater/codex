<template>
  <vue-pdf-embed
    class="pdfPage"
    :class="fitToClass"
    :page="1"
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
import { mapActions } from "pinia";
import VuePdfEmbed from "vue-pdf-embed";

import { useReaderStore } from "@/stores/reader";

export default {
  name: "PDFPage",
  components: { VuePdfEmbed },
  props: {
    pk: { type: Number, required: true },
    src: {
      type: String,
      required: true,
    },
    settings: {
      type: Object,
      required: true,
    },
    fitToClass: {
      type: Object,
      required: true,
    },
  },
  emits: ["load", "error", "unauthorized"],
  data() {
    return {
      innerHeight: window.innerHeight,
      innerWidth: window.innerWidth,
    };
  },
  computed: {
    width() {
      // Wide PDFs will not fit to SCREEN well.
      // vue-pdf-embed internal canvas sizing algorithm makes this difficult.
      // Maybe not impossible but I'm lazy right now.
      let width = ["WIDTH"].includes(this.settings.fitTo) ? this.innerWidth : 0;
      if (this.settings.twoPages) {
        width = width / 2;
      }
      return width;
    },
    height() {
      return ["HEIGHT", "SCREEN"].includes(this.settings.fitTo)
        ? this.innerHeight
        : 0;
    },
  },
  mounted() {
    window.addEventListener("resize", this.onResize);
  },
  unmounted() {
    window.removeEventListener("resize", this.onResize);
  },
  methods: {
    ...mapActions(useReaderStore, ["routeToPage"]),
    onResize() {
      this.innerHeight = window.innerHeight;
      this.innerWidth = window.innerWidth;
    },
  },
};
</script>

<style scoped lang="scss">
.pdfPage {
  display: inline-block;
}

/* bugfixes for vue-pdf-embed */
:deep(.vue-pdf-embed.fitToHeightTwo > div > canvas),
:deep(.vue-pdf-embed.fitToScreenTwo > div > canvas) {
  width: inherit !important;
}
:deep(.vue-pdf-embed.fitToScreen > div > canvas),
:deep(.vue-pdf-embed.fitToScreenTwo > div > canvas) {
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

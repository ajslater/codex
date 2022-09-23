<template>
  <vue-pdf-embed
    :key="key"
    :disable-annotation-layer="false"
    :disable-text-layer="false"
    class="pdfPage"
    :class="classes"
    :page="1"
    :source="source"
    :width="width"
    :height="height"
  />
</template>

<script>
import { mapState } from "pinia";
import VuePdfEmbed from "vue-pdf-embed/dist/vue2-pdf-embed";

import { useReaderStore } from "@/stores/reader";

export default {
  name: "PDFPage",
  components: { VuePdfEmbed },
  props: {
    source: {
      type: String,
      required: true,
    },
    classes: {
      type: Object,
      default: undefined,
    },
  },
  computed: {
    ...mapState(useReaderStore, {
      width(state) {
        // Wide PDFs will not fit to SCREEN well.
        // vue-pdf-embed internal canvas sizing algorithm makes this difficult.
        // Maybe not impossible but I'm lazy right now.
        let width = ["WIDTH"].includes(state.computedSettings.fitTo)
          ? window.innerWidth
          : 0;
        if (state.computedSettings.twoPages) {
          width = width / 2;
        }
        return width;
      },
      height(state) {
        return ["HEIGHT", "SCREEN"].includes(state.computedSettings.fitTo)
          ? window.innerHeight
          : 0;
      },
      key(state) {
        // Force render when settings change.
        return JSON.stringify(state.computedSettings);
      },
    }),
  },
};
</script>

<style scoped lang="scss">
.pdfPage {
  display: inline-flex;
}
.fitToHeight,
.fitToOrig,
.fitToScreen {
  position: relative;
  align-self: center;
}
.fitToHeightTwo,
.fitToOrigTwo,
.fitToScreenTwo {
}
.fitToWidthTwo {
}
</style>

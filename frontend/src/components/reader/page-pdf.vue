<template>
  <vue-pdf-embed
    ref="pdfembed"
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
import { mapActions, mapGetters, mapState } from "pinia";
import VuePdfEmbed from "vue-pdf-embed/dist/vue2-pdf-embed";

import { useReaderStore } from "@/stores/reader";

export default {
  name: "PDFPage",
  components: { VuePdfEmbed },
  props: {
    src: {
      type: String,
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
    ...mapGetters(useReaderStore, ["fitToClass"]),
    ...mapState(useReaderStore, {
      width(state) {
        // Wide PDFs will not fit to SCREEN well.
        // vue-pdf-embed internal canvas sizing algorithm makes this difficult.
        // Maybe not impossible but I'm lazy right now.
        let width = ["WIDTH"].includes(state.computedSettings.fitTo)
          ? this.innerWidth
          : 0;
        if (state.computedSettings.twoPages) {
          width = width / 2;
        }
        return width;
      },
      height(state) {
        return ["HEIGHT", "SCREEN"].includes(state.computedSettings.fitTo)
          ? this.innerHeight
          : 0;
      },
    }),
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
</style>

<!-- eslint-disable-next-line vue-scoped-css/enforce-style-type -->
<style lang="scss">
/* bugfixes for vue-pdf-embed */
.vue-pdf-embed.fitToHeightTwo > div > canvas,
.vue-pdf-embed.fitToScreenTwo > div > canvas {
  width: inherit !important;
}
.vue-pdf-embed.fitToWidthTwo > div > canvas {
  height: inherit !important;
}
.vue-pdf-embed.fitToOrigTwo > div > canvas {
  height: inherit !important;
  width: inherit !important;
}
</style>

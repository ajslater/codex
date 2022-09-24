<template>
  <div>
    <Placeholder
      class="placeholder"
      :class="{ hidden: rendered }"
      :size="placeholderSize"
    />
    <vue-pdf-embed
      :key="key"
      ref="pdfembed"
      :disable-annotation-layer="false"
      :disable-text-layer="false"
      class="pdfPage"
      :class="fitToClass"
      :page="1"
      :source="source"
      :width="width"
      :height="height"
      @rendered="onRendered"
      @internal-link-clicked="routeToPage"
    />
  </div>
</template>

<script>
import { mapActions, mapGetters, mapState } from "pinia";
import VuePdfEmbed from "vue-pdf-embed/dist/vue2-pdf-embed";

import Placeholder from "@/components/placeholder-loading.vue";
import { useReaderStore } from "@/stores/reader";

const PLACEHOLDER_ENGAGE_MS = 333;

export default {
  name: "PDFPage",
  components: { Placeholder, VuePdfEmbed },
  props: {
    source: {
      type: String,
      required: true,
    },
  },
  data() {
    return {
      rendered: false,
      startedLoading: 0,
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
    placeholderSize() {
      const maxDimension = Math.min(window.innerHeight, window.innerWidth);
      return Number.parseInt(maxDimension / 2);
    },
  },
  watch: {
    $route() {
      this.onStartedLoading();
    },
  },
  methods: {
    ...mapActions(useReaderStore, ["routeToPage"]),
    onStartedLoading() {
      this.startedLoading = true;
      setTimeout(function () {
        if (this.startedLoading) {
          this.rendered = false;
        }
      }, PLACEHOLDER_ENGAGE_MS);
    },
    onRendered() {
      this.startedLoading = 0;
      this.rendered = true;
    },
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
.placeholder {
  position: absolute;
  top: 50%;
  left: 50%;
  transform: translate(-50%, -50%);
  z-index: 20;
}
.hidden {
  display: none;
}
</style>

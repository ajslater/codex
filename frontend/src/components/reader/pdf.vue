<template>
  <div>
    <div v-if="error">
      <div id="failed">
        {{ error.text }}
      </div>
      <v-icon id="failedIcon">{{ error.icon }}</v-icon>
    </div>
    <div v-else>
      <vue-pdf-embed
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
        @loading-failed="failed"
        @rendering-failed="failed"
        @password-requested="unauthorized"
      />
      <Placeholder
        v-if="!rendered"
        class="placeholder"
        :size="placeholderSize"
      />
    </div>
  </div>
</template>

<script>
import { mdiAlertCircleOutline, mdiLockOutline } from "@mdi/js";
import { mapActions, mapGetters, mapState } from "pinia";
import VuePdfEmbed from "vue-pdf-embed/dist/vue2-pdf-embed";

import { getComicPageSource } from "@/api/v3/reader";
import Placeholder from "@/components/placeholder-loading.vue";
import { useReaderStore } from "@/stores/reader";

const PLACEHOLDER_ENGAGE_MS = 333;

export default {
  name: "PDFPage",
  components: { Placeholder, VuePdfEmbed },
  props: {
    pk: {
      type: Number,
      required: true,
    },
    page: {
      type: Number,
      required: true,
    },
  },
  data() {
    return {
      rendered: false,
      startedLoading: 0,
      error: false,
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
      source(state) {
        const params = { pk: this.pk, page: this.page };
        return getComicPageSource(params, state.timestamp);
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
      this.error = false;
    },
    failed() {
      this.error = {
        text: "Failed to load PDF",
        icon: mdiAlertCircleOutline,
      };
    },
    unauthorized() {
      this.error = { text: "Protected PDF", icon: mdiLockOutline };
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
  z-index: 5;
}
#failed {
  color: #505050;
  font-size: 72px;
  text-align: center;
  position: fixed;
  top: 50%;
  left: 50%;
  transform: translate(-50%, -50%);
}
#failedIcon {
  position: absolute;
  top: 50%;
  left: 50%;
  transform: translate(-50%, -50%);
  color: darkred;
}
</style>
<!-- eslint-disable-next-line vue-scoped-css/enforce-style-type -->
<style lang="scss">
$iconsize: calc(100vw / 2);
#failedIcon svg {
  width: $iconsize;
  height: $iconsize;
  font-size: $iconsize;
  opacity: 0.33;
}
</style>

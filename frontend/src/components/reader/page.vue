<template>
  <div class="page">
    <ErrorPage v-if="error" :type="error" />
    <LoadingPage v-else-if="showProgress && !loaded" />
    <component
      :is="component"
      v-else
      :src="src"
      @error="onError"
      @load="onLoad"
      @unauthorized="onUnauthorized"
    />
  </div>
</template>

<script>
import { mapGetters, mapState } from "pinia";

import { getComicPageSource } from "@/api/v3/reader";
import Placeholder from "@/components/placeholder-loading.vue";
import LoadingPage from "@/components/reader/page-loading.vue";
import { useReaderStore } from "@/stores/reader";
const PDFPage = () => import("@/components/reader/page-pdf.vue");
import ErrorPage from "@/components/reader/page-error.vue";
import ImgPage from "@/components/reader/page-img.vue";

const PROGRESSS_DELAY_MS = 333;

export default {
  name: "BookPage",
  components: { Placeholder, ErrorPage, LoadingPage },
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
      showProgress: false,
      loaded: false,
      error: false,
    };
  },
  computed: {
    ...mapGetters(useReaderStore, ["fitToClass"]),
    ...mapState(useReaderStore, {
      src(state) {
        const params = { pk: this.pk, page: this.page };
        return getComicPageSource(params, state.timestamp);
      },
      component(state) {
        const isPDF = state.comic ? state.comic.fileFormat === "pdf" : false;
        return isPDF ? PDFPage : ImgPage;
      },
    }),
  },
  mounted() {
    setTimeout(function () {
      if (!this.loaded) {
        this.loading = true;
      }
    }, PROGRESSS_DELAY_MS);
  },
  methods: {
    onLoad() {
      this.showProgress = false;
      this.loaded = true;
      this.error = false;
    },
    onError() {
      this.error = "load";
      this.showProgress = false;
    },
    onUnauthorized() {
      this.error = "unauthorized";
      this.showProgress = false;
    },
  },
};
</script>

<style scoped lang="scss">
.page {
  display: inline;
}
</style>

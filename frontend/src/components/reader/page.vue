<template>
  <div class="page">
    <ErrorPage v-if="error" :two-pages="settings.twoPages" :type="error" />
    <LoadingPage
      v-else-if="showProgress && !loaded"
      :two-pages="settings.twoPages"
    />
    <component
      :is="component"
      v-else
      :pk="book.pk"
      :src="src"
      :settings="settings"
      :fit-to-class="fitToClass"
      @error="onError"
      @load="onLoad"
      @unauthorized="onUnauthorized"
    />
  </div>
</template>

<script>
import { defineAsyncComponent, markRaw } from "vue";

import { getComicPageSource } from "@/api/v3/reader";
import Placeholder from "@/components/placeholder-loading.vue";
import LoadingPage from "@/components/reader/page-loading.vue";
const PDFPage = markRaw(
  defineAsyncComponent(() => import("@/components/reader/page-pdf.vue"))
);
import ErrorPage from "@/components/reader/page-error.vue";
import ImgPage from "@/components/reader/page-img.vue";

const PROGRESSS_DELAY_MS = 333;

export default {
  name: "BookPage",
  components: { Placeholder, ErrorPage, LoadingPage },
  props: {
    book: {
      type: Object,
      required: true,
    },
    page: {
      type: Number,
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
  data() {
    return {
      showProgress: false,
      loaded: false,
      error: false,
    };
  },
  computed: {
    src() {
      const params = { pk: this.book.pk, page: this.page };
      return getComicPageSource(params);
    },
    component() {
      const isPDF = this.book.fileFormat === "pdf";
      return isPDF ? PDFPage : ImgPage;
    },
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

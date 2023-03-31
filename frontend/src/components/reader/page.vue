<template>
  <div :id="`page${page}`" :data-page="page" :class="pageClass">
    <ErrorPage v-if="error" :two-pages="settings.twoPages" :type="error" />
    <LoadingPage
      v-else-if="showProgress && !loaded"
      :two-pages="settings.twoPages"
    />
    <component
      :is="component"
      v-else
      :src="src"
      :fit-to-class="fitToClass"
      :book="book"
      @error="onError"
      @load="onLoad"
      @unauthorized="onUnauthorized"
    />
  </div>
</template>

<script>
import { mapActions } from "pinia";
import { defineAsyncComponent, markRaw } from "vue";

import { getComicPageSource } from "@/api/v3/reader";
import Placeholder from "@/components/placeholder-loading.vue";
import LoadingPage from "@/components/reader/page-loading.vue";
import { useReaderStore } from "@/stores/reader";
const PDFPage = markRaw(
  defineAsyncComponent(() => import("@/components/reader/page-pdf.vue"))
);
import ErrorPage from "@/components/reader/page-error.vue";
import ImgPage from "@/components/reader/page-img.vue";

const PROGRESSS_DELAY_MS = 333;

const FIT_TO_CHOICES = { S: "Screen", W: "Width", H: "Height", O: "Original" };

export default {
  name: "BookPage",
  components: { Placeholder, ErrorPage, LoadingPage, PDFPage, ImgPage },
  props: {
    book: {
      type: Object,
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
    pageClass() {
      return this.settings.vertical ? "pageVertical" : "pageHorizontal";
    },
    fitToClass() {
      let classes = {};
      const fitTo = FIT_TO_CHOICES[this.settings.fitTo];
      if (fitTo) {
        let fitToClass = "fitTo";
        fitToClass +=
          fitTo.charAt(0).toUpperCase() + fitTo.slice(1).toLowerCase();
        if (this.settings.twoPages) {
          fitToClass += "Two";
          if (this.settings.vertical) {
            fitToClass += "Vertical";
          }
        }
        classes[fitToClass] = true;
      }
      return classes;
    },
    src() {
      const params = { pk: this.book.pk, page: this.page };
      return getComicPageSource(params);
    },
    component() {
      const isPDF = this.book.fileType === "PDF";
      return isPDF ? PDFPage : ImgPage;
    },
    settings() {
      return this.getSettings(this.book);
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
    ...mapActions(useReaderStore, ["getSettings"]),
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
.pageHorizontal {
  display: inline;
}
.pageVertical {
  display: block;
}
</style>

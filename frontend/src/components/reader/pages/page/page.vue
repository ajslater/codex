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
      :book="book"
      :fit-to-class="fitToClass"
      :page="1"
      :src="src"
      @error="onError"
      @load="onLoad"
      @unauthorized="onUnauthorized"
    />
  </div>
</template>

<script>
import { mapActions, mapGetters } from "pinia";
import titleize from "titleize";
import { defineAsyncComponent, markRaw } from "vue";

import { getComicPageSource } from "@/api/v3/reader";
import LoadingPage from "@/components/reader/pages/page/page-loading.vue";
import { useReaderStore } from "@/stores/reader";
const PDFPage = markRaw(
  defineAsyncComponent(() => import("@/components/reader/pages/page/pdf.vue")),
);
import ErrorPage from "@/components/reader/pages/page/page-error.vue";
import ImgPage from "@/components/reader/pages/page/page-img.vue";

const PROGRESSS_DELAY_MS = 333;

const FIT_TO_CHOICES = { S: "Screen", W: "Width", H: "Height", O: "Original" };

export default {
  name: "BookPage",
  components: { ErrorPage, LoadingPage, PDFPage, ImgPage },
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
    ...mapGetters(useReaderStore, ["isVertical"]),
    pageClass() {
      return this.isVertical ? "pageVertical" : "pageHorizontal";
    },
    fitToClass() {
      let classes = {};
      const fitTo = FIT_TO_CHOICES[this.settings.fitTo];
      if (fitTo) {
        let fitToClass = "fitTo";
        fitToClass += titleize(fitTo);
        if (this.isVertical) {
          fitToClass += "Vertical";
        } else if (this.settings.twoPages) {
          fitToClass += "Two";
        }
        classes[fitToClass] = true;
      }
      return classes;
    },
    src() {
      const params = {
        pk: this.book.pk,
        page: this.page,
        mtime: this.book.mtime,
      };
      return getComicPageSource(params);
    },
    component() {
      return this.book.fileType === "PDF" ? PDFPage : ImgPage;
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
  font-size: 0;
}

.pageVertical {
  display: block;
  font-size: 0;
}
</style>

<template>
  <div
    :id="`page${page}`"
    :key="ts"
    :data-page="page"
    class="page"
    :style="style"
  >
    <ErrorPage
      v-if="error"
      :two-pages="twoPages"
      :type="error"
      @retry="onRetry"
    />
    <LoadingPage v-else-if="showProgress && !loaded" :two-pages="twoPages" />
    <component
      :is="component"
      v-else
      ref="pageComponent"
      :book="book"
      :page="1"
      :src="src"
      @error="onError"
      @load="onLoad"
      @unauthorized="onUnauthorized"
    />
  </div>
</template>

<script>
import { mapActions, mapState } from "pinia";
import { defineAsyncComponent, markRaw } from "vue";

import { getComicPageSource } from "@/api/v3/reader";
import LoadingPage from "@/components/reader/pager/page/page-loading.vue";
import { useReaderStore } from "@/stores/reader";
const PDFDoc = markRaw(
  defineAsyncComponent(() => import("@/components/reader/pager/pdf-doc.vue")),
);
import ErrorPage from "@/components/reader/pager/page/page-error.vue";
import ImgPage from "@/components/reader/pager/page/page-img.vue";

const PROGRESS_DELAY_MS = 333;

export default {
  name: "BookPage",
  components: { ErrorPage, LoadingPage, PDFDoc, ImgPage },
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
      error: "",
      ts: 0,
    };
  },
  computed: {
    ...mapState(useReaderStore, {
      scale: (state) => state.clientSettings.scale,
    }),
    style() {
      // Magic for transform: scale() not sizing elements right.
      const s = {};
      if (this.book.fileType === "PDF" || this.scale == 1) {
        return s;
      }
      const img = this.$refs.pageComponent?.$el;
      if (!img?.naturalHeight) {
        return s;
      }
      s.height = img.naturalHeight * this.scale + "px";
      s.width = img.naturalWidth * this.scale + "px";
      return s;
    },
    src() {
      const mtime = Math.max(this.book.mtime, this.ts);
      const params = {
        pk: this.book.pk,
        page: this.page,
        mtime,
      };
      return getComicPageSource(params);
    },
    component() {
      return this.book.fileType === "PDF" ? PDFDoc : ImgPage;
    },
    bookSettings() {
      return this.getBookSettings(this.book);
    },
    twoPages() {
      return this.bookSettings.twoPages;
    },
  },
  mounted() {
    setTimeout(function () {
      if (!this.loaded) {
        this.loading = true;
      }
    }, PROGRESS_DELAY_MS);
  },
  methods: {
    ...mapActions(useReaderStore, ["getBookSettings"]),
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
    onRetry() {
      this.ts = Date.now();
    },
  },
};
</script>

<style scoped lang="scss">
.page {
  font-size: 0;
}
</style>

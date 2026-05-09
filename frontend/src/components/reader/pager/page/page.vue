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
    <template v-else>
      <!--
        Keep the image component mounted whenever ``showProgress``
        flips on. The previous ``v-else-if`` chain unmounted it the
        moment the 333ms timer fired, ripping out the ``<img>`` —
        and with it the ``@load`` listener — before the response
        arrived. On a slow first request (production: nginx in
        front, cold caches) the response would land on a torn-down
        element, ``loaded`` never flipped, and the spinner stuck
        forever. ``v-show`` keeps the element in the tree so the
        listener fires.
      -->
      <component
        :is="component"
        v-show="!showProgress || loaded"
        ref="pageComponent"
        :book="book"
        :page="1"
        :src="src"
        @error="onError"
        @load="onLoad"
        @unauthorized="onUnauthorized"
      />
      <LoadingPage v-if="showProgress && !loaded" :two-pages="twoPages" />
    </template>
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
      /*
       * ``true`` once we've seen an ``<img>`` load fail on a PDF
       * book — the response was ``application/pdf`` (the detector
       * declined to serve as image), so we re-mount the page through
       * ``<PDFDoc>`` against the same URL with ``?format=pdf``.
       */
      pdfFallback: false,
    };
  },
  computed: {
    ...mapState(useReaderStore, {
      scale: (state) => state.clientSettings?.scale,
      pdfRenderMode: (state) => state.clientSettings?.pdfRenderMode || "auto",
    }),
    isPDF() {
      return this.book.fileType === "PDF";
    },
    style() {
      // Magic for transform: scale() not sizing elements right.
      const s = {};
      if (this.usingPDFDoc || this.scale == 1) {
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
        format: this.activeFormat,
      };
      return getComicPageSource(params);
    },
    activeFormat() {
      /*
       * For non-PDF books the format param is ignored by the
       * backend; we still pass it through so the URL is stable.
       */
      if (!this.isPDF) {
        return "auto";
      }
      if (this.pdfFallback) {
        // Image attempt failed → re-fetch with PDF response.
        return "pdf";
      }
      return this.pdfRenderMode;
    },
    usingPDFDoc() {
      /*
       * Render through ``<PDFDoc>`` when:
       *   • the user explicitly forced PDF rendering, or
       *   • the ``<img>`` first attempt failed for a PDF book.
       */
      return this.isPDF && (this.pdfRenderMode === "pdf" || this.pdfFallback);
    },
    component() {
      return this.usingPDFDoc ? PDFDoc : ImgPage;
    },
    bookSettings() {
      return this.getBookSettings(this.book);
    },
    twoPages() {
      return this.bookSettings?.twoPages ?? false;
    },
  },
  watch: {
    /*
     * If the user toggles render mode mid-read, drop the fallback flag
     * so the new mode takes effect on the next mount.
     */
    pdfRenderMode() {
      this.pdfFallback = false;
      this.error = "";
      this.loaded = false;
    },
  },
  mounted() {
    /*
     * Show the spinner only if the image is still loading after
     * ``PROGRESS_DELAY_MS``. Two corrections from the original:
     *
     * 1. Arrow function preserves ``this``. The original
     *    ``setTimeout(function () { ... })`` ran with the timer's
     *    context, not the component's, so ``this.loaded`` and the
     *    write below were no-ops.
     * 2. ``this.showProgress`` is what the template binds; the
     *    original wrote to ``this.loading`` which has never been a
     *    data field on this component, so the spinner literally
     *    never appeared.
     *
     * Stash the timer ID so ``beforeUnmount`` can clear it — a
     * fast page swap mid-delay would otherwise fire the write on a
     * torn-down component.
     */
    this._loadingTimer = setTimeout(() => {
      if (!this.loaded) {
        this.showProgress = true;
      }
    }, PROGRESS_DELAY_MS);
  },
  beforeUnmount() {
    clearTimeout(this._loadingTimer);
  },
  methods: {
    ...mapActions(useReaderStore, ["getBookSettings"]),
    onLoad() {
      this.showProgress = false;
      this.loaded = true;
      this.error = false;
    },
    onError() {
      /*
       * For PDF books on the first ``<img>`` attempt, the failure
       * means the backend sent ``application/pdf`` — the detector
       * declined to serve as image. Swap to ``<PDFDoc>`` against
       * the same URL and let it render via vue-pdf-embed. For all
       * other failures, surface the error.
       */
      if (this.isPDF && !this.pdfFallback && !this.usingPDFDoc) {
        this.pdfFallback = true;
        this.loaded = false;
        return;
      }
      this.error = "load";
      this.showProgress = false;
    },
    onUnauthorized() {
      this.error = "unauthorized";
      this.showProgress = false;
    },
    onRetry() {
      this.ts = Date.now();
      this.pdfFallback = false;
      this.error = "";
    },
  },
};
</script>

<style scoped lang="scss">
.page {
  font-size: 0;
}
</style>

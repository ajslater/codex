<template>
  <ScaleForScroll>
    <v-virtual-scroll
      id="verticalScroll"
      :key="isReadInReverse"
      ref="verticalScroll"
      v-scroll:#verticalScroll="onScroll"
      :items="items"
      :height="innerHeight"
      :width="innerWidth"
    >
      <template #default="{ item }">
        <BookPage :book="book" :page="item" class="verticalPage" />
        <div
          v-intersect.quiet="intersectOptions"
          class="pageTracker"
          :class="{ pageTrackerToolbars: showToolbars }"
          :data-page="item"
        />
      </template>
    </v-virtual-scroll>
  </ScaleForScroll>
</template>

<script>
import { mapActions, mapState, mapWritableState } from "pinia";

import BookPage from "@/components/reader/pager/page/page.vue";
import ScaleForScroll from "@/components/reader/pager/scale-for-scroll.vue";
import { useReaderStore } from "@/stores/reader";
import { range } from "@/util";

const TIMEOUT = 250;

export default {
  name: "PagerVertical",
  components: {
    BookPage,
    ScaleForScroll,
  },
  props: {
    book: { type: Object, required: true },
  },
  data() {
    return {
      /*
       * If the window is small on mount, the intersection observer
       * goes crazy and scrolls to 0.
       */
      innerHeight: window.innerHeight,
      innerWidth: window.innerWidth,
      intersectorOn: false,
      programmaticScroll: false,
      intersectOptions: {
        handler: this.onIntersect,
        options: { threshold: [0.75] },
      },
    };
  },
  computed: {
    ...mapState(useReaderStore, {
      storePage: (state) => state.page,
      showToolbars: (state) => state.showToolbars,
    }),
    ...mapWritableState(useReaderStore, ["reactWithScroll"]),
    bookSettings() {
      return this.getBookSettings(this.book);
    },
    isReadInReverse() {
      return this.bookSettings.isReadInReverse;
    },
    items() {
      const len = this.book?.maxPage ? this.book.maxPage + 1 : 0;
      const pages = range(0, len);
      if (this.isReadInReverse) {
        pages.reverse();
      }
      return pages;
    },
  },
  watch: {
    storePage(to) {
      if (this.reactWithScroll) {
        this.scrollToPage(to);
      }
    },
  },
  mounted() {
    window.addEventListener("resize", this.onResize);
    setTimeout(() => {
      this.scrollToPage(this.storePage);
    }, TIMEOUT);
  },
  beforeUnmount() {
    window.removeEventListener("resize", this.onResize);
  },
  methods: {
    ...mapActions(useReaderStore, [
      "getBookSettings",
      "setActivePage",
      "setBookChangeFlag",
    ]),
    onIntersect(isIntersecting, entries) {
      if (isIntersecting && this.intersectorOn) {
        const entry = entries[0];
        const page = +entry.target.dataset.page;
        this.setActivePage(page, false);
      }
    },
    onScroll() {
      if (this.programmaticScroll) {
        return;
      }
      this.intersectorOn = true;
      const el = this.$refs.verticalScroll.$el;
      const scrollTop = el.scrollTop;
      if (this.storePage === 0 && scrollTop === 0) {
        this.setBookChangeFlag("prev");
      } else if (this.storePage === this.book.maxPage) {
        const scrollTopMax = el.scrollTopMax || el.scrollHeight - el.clientTop;

        if (window.innerHeight + scrollTop + 1 >= scrollTopMax) {
          this.setBookChangeFlag("next");
        }
      }
    },
    scrollToPage(page) {
      this.intersectorOn = false;
      this.programmaticScroll = true;
      const vs = this.$refs.verticalScroll;
      if (vs) {
        vs.scrollToIndex(page);
      } else {
        console.debug("Can't find verticalScroll component.");
      }
      setTimeout(() => {
        this.programmaticScroll = false;
      }, TIMEOUT);
    },
    onResize() {
      this.innerHeight = window.innerHeight;
      this.innerWidth = window.innerWidth;
    },
  },
};
</script>
<style scoped lang="scss">
.verticalPage {
  display: block;
}

:deep(.v-virtual-scroll__item) {
  position: relative;
}

$pageTrackerBaseHeight: calc(100vh - env(safe-area-inset-bottom));

.pageTracker {
  position: absolute;
  top: 0;
  //left: 2.5%;
  z-index: 15;
  width: 100%;
  // viewport height - toolbars - mobile buffer.
  height: calc($pageTrackerBaseHeight * 0.95);
  // For debugging
  /*
  background-color: green;
  opacity: 0.25;
  border: dashed 10px red;
  */
}

.pageTrackerToolbars {
  height: calc(($pageTrackerBaseHeight - 154px - 32px) * 0.95) !important;
}
</style>

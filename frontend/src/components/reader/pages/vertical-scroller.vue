<template>
  <v-virtual-scroll
    id="verticalScroll"
    ref="verticalScroll"
    v-scroll:#verticalScroll="onScroll"
    :items="items"
    :height="innerHeight"
    :width="innerWidth"
  >
    <!--
    :item-height="itemHeight"
    dynamic itemHeight solves the jumpy scroll issue,
    but throws a recursive warning.
    -->
    <template #default="{ item }">
      <BookPage :book="book" :page="item" />
      <div
        v-intersect.quiet="{
          handler: onIntersect,
          options: intersectOptions,
        }"
        class="pageTracker"
        :data-page="item"
      />
    </template>
  </v-virtual-scroll>
</template>

<script>
import _ from "lodash";
import { mapActions, mapState, mapWritableState } from "pinia";

import BookPage from "@/components/reader/pages/page/page.vue";
import { useReaderStore } from "@/stores/reader";

const MAX_VISIBLE_PAGES = 12;
const TIMEOUT = 250;
const INTERECT_OPTIONS_FIT_TO_HEIGHT = { threshold: [0.75] };
const INTERSECT_OPTIONS = {
  S: INTERECT_OPTIONS_FIT_TO_HEIGHT,
  H: INTERECT_OPTIONS_FIT_TO_HEIGHT,
};

export default {
  name: "PagesVerticalScroller",
  components: {
    BookPage,
  },
  props: {
    book: { type: Object, required: true },
  },
  data() {
    return {
      // If the window is small on mount, the intersection observer
      // goes crazy and scrolls to 0.
      innerHeight: window.innerHeight,
      innerWidth: window.innerWidth,
      intersectorOn: false,
      programmaticScroll: false,
    };
  },
  computed: {
    ...mapState(useReaderStore, {
      storePage: (state) => state.page,
    }),
    ...mapWritableState(useReaderStore, ["reactWithScroll"]),
    settings() {
      return this.getSettings(this.book);
    },
    readInReverse() {
      return this.settings.readInReverse;
    },
    items() {
      const len = this.book?.maxPage + 1 ?? 0;
      const pages = _.range(0, len);
      if (this.readInReverse) {
        pages.reverse();
      }
      return pages;
    },
    visibleItems() {
      return Math.min(this.book?.maxPage ?? 0, MAX_VISIBLE_PAGES);
    },
    intersectOptions() {
      return INTERSECT_OPTIONS[this.settings.fitTo];
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
      "setActivePage",
      "setBookChangeFlag",
      "getSettings",
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
        console.debug("Can't find vertcalScroll component.");
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
:deep(.v-virtual-scroll__item) {
  position: relative;
}
.pageTracker {
  position: absolute;
  top: 0;
  left: 0;
  z-index: 15;
  width: 95vw;
  height: 100%;
  // TODO, somehow get it horizontally fixed.
  /*
  // For debugging
  background-color: green;
  opacity: 0.25;
  border: dashed 10px red;
  */
}
</style>

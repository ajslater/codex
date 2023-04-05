<template>
  <v-virtual-scroll
    id="verticalScroll"
    ref="verticalScroll"
    v-scroll:#verticalScroll="onScroll"
    :items="items"
    :visible-items="visibleItems"
    :height="innerHeight"
    :width="innerWidth"
    :item-height="itemHeight"
  >
    <!--
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
import { mapActions, mapGetters, mapState } from "pinia";
import { VVirtualScroll } from "vuetify/labs/VVirtualScroll";

import BookPage from "@/components/reader/page.vue";
import { useReaderStore } from "@/stores/reader";

const MODAL_COMIC_RATIO = 1.537_223_340_040_241_5;
const MAX_VISIBLE_PAGES = 8;

export default {
  name: "PagesScrollerVertical",
  components: {
    BookPage,
    VVirtualScroll,
  },
  props: {
    book: { type: Object, required: true },
  },
  data() {
    return {
      mountedTime: 0,
      // If the window is small on mount, the intersection observer
      // goes crazy and scrolls to 0.
      innerHeight: window.innerHeight,
      innerWidth: window.innerWidth,
    };
  },
  computed: {
    ...mapGetters(useReaderStore, ["isOnCoverPage"]),
    ...mapState(useReaderStore, {
      prevBook: (state) => state.routes.books?.prev,
      nextBook: (state) => state.routes.books?.next,
      storePage: (state) => state.page,
      storePk: (state) => state.pk,
    }),
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
    itemHeight() {
      const fitTo = this.settings.fitTo;
      let height = window.innerHeight;
      if (fitTo === "W") {
        height = height * MODAL_COMIC_RATIO;
      } else if (fitTo == "O") {
        height = height * 2;
      }
      return height;
    },
    intersectOptions() {
      const fitTo = this.settings.fitTo;
      let options;
      options =
        fitTo === "S" || fitTo === "H"
          ? {
              threshold: [0.75],
            }
          : undefined;
      return options;
    },
  },
  mounted() {
    window.addEventListener("resize", this.onResize);
    this.setPage(this.storePage, true);
    this.mountedTime = Date.now();
  },
  beforeUnmount() {
    window.removeEventListener("resize", this.onResize);
  },
  methods: {
    ...mapActions(useReaderStore, [
      "setActivePage",
      "setBookChangeFlag",
      "setPage",
      "getSettings",
    ]),
    onIntersect(isIntersecting, entries) {
      if (isIntersecting) {
        const entry = entries[0];
        const page = +entry.target.dataset.page;
        this.setActivePage(page);
        // console.log(isIntersecting, page, entries[0].intersectionRatio);
      }
    },
    onScroll() {
      if (Date.now() - this.mountedTime < 2) {
        // Don't show scrolly book change drawers immediately on load.
        return;
      }
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
  width: 90vw;
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

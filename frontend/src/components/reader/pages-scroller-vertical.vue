<template>
  <v-virtual-scroll
    id="verticalScroll"
    v-scroll#target="onScroll"
    :items="items"
    :visible-items="visibleItems"
    :height="innerHeight"
    :width="innerWidth"
    :item-height="innerHeight"
  >
    <template #default="{ item }">
      <BookPage
        v-intersect.quiet="{
          handler: onIntersect,
          options: {
            threshold: [0.01],
            rootMargin: '-40%',
          },
        }"
        :book="book"
        :page="item"
      />
    </template>
  </v-virtual-scroll>
</template>

<script>
// 5 is the magic number to avoid disappearing items at the midpoint.
import _ from "lodash";
import { mapActions, mapGetters, mapState } from "pinia";
import { VVirtualScroll } from "vuetify/labs/VVirtualScroll";

import BookPage from "@/components/reader/page.vue";
import { useReaderStore } from "@/stores/reader";

export default {
  name: "PagesScrollerVertical",
  components: {
    BookPage,
    VVirtualScroll,
  },
  props: {
    book: { type: Object, required: true },
  },
  emits: ["click"],
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
      return Math.min(this.book?.maxPage ?? 0, 5);
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
      }
    },
    onScroll() {
      if (Date.now() - this.mountedTime < 2) {
        // Don't show scrolly book change drawers immediately on load.
        return;
      }
      if (this.storePage === 0 && window.scrollY === 0) {
        this.setBookChangeFlag("prev");
      } else if (
        this.storePage === this.book.maxPage &&
        window.innerHeight + window.scrollY + 1 >= document.body.scrollHeight
      ) {
        this.setBookChangeFlag("next");
      }
    },
    onResize() {
      this.innerHeight = window.innerHeight;
      this.innerWidth = window.innerWidth;
    },
  },
};
</script>

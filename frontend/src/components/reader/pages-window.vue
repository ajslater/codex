<template>
  <v-window show-arrows :model-value="activePage">
    <template #prev>
      <PageChangeLink direction="prev" />
    </template>
    <template #next>
      <PageChangeLink direction="next" />
    </template>
    <v-window-item
      v-for="page of pages"
      :key="`c/${book.pk}/${page}`"
      class="windowItem"
      disabled
      :eager="page >= activePage - 1 && page <= activePage + 2"
      :model-value="page"
      :transition="true"
      :reverse-transition="readInReverse"
    >
      <BookPage
        v-if="!readInReverse || (secondPage && page < book.maxPage)"
        :book="book"
        :settings="settings"
        :fit-to-class="fitToClass"
        :page="readInReverse ? page + 1 : page"
      />
      <BookPage
        v-if="readInReverse || (secondPage && page < book.maxPage)"
        :book="book"
        :settings="settings"
        :fit-to-class="fitToClass"
        :page="readInReverse ? page : page + 1"
      />
    </v-window-item>
  </v-window>
</template>

<script>
import _ from "lodash";
import { mapActions, mapGetters, mapState } from "pinia";

import BookPage from "@/components/reader/page.vue";
import PageChangeLink from "@/components/reader/page-change-link.vue";
import { useReaderStore } from "@/stores/reader";

export default {
  name: "PagesWindow",
  components: {
    BookPage,
    PageChangeLink,
  },
  props: {
    book: { type: Object, required: true },
  },
  emits: ["click"],
  data() {
    return {
      activePage: undefined,
    };
  },
  computed: {
    ...mapGetters(useReaderStore, ["isOnCoverPage"]),
    ...mapState(useReaderStore, {
      bookRoutes: (state) => state.routes.books,
      settings(state) {
        const book = state.books.get(this.book.pk);
        return state.getSettings(state.readerSettings, book);
      },
      prevBookPk: (state) => state.routes.books?.prev.pk,
      twoPages: (state) => state.activeSettings.twoPages,
      readInReverse: (state) => state.activeSettings.readInReverse,
    }),
    fitToClass() {
      return this.getFitToClass(this.settings);
    },
    pages() {
      const len = this.book?.maxPage + 1 ?? 0;
      return _.range(0, len);
    },
    secondPage() {
      return this.settings.twoPages && !this.isOnCoverPage;
    },
  },
  watch: {
    $route(to) {
      if (+to.params.pk === this.book.pk) {
        this.setActivePageForRoute(+to.params.page);
      }
    },
    twoPages() {
      this.setActivePageForRoute(+this.$route.params.page);
    },
  },
  created() {
    let page;
    if (this.book.pk === +this.$route.params.pk) {
      // Active Book
      page = +this.$route.params.page;
    } else if (this.book.pk === this.prevBookPk) {
      // Prev Book
      page = this.book.maxPage;
    } else {
      // Must be next book
      page = 0;
    }
    this.activePage = page;
  },
  methods: {
    ...mapActions(useReaderStore, [
      "routeToPage",
      "setRoutesAndBookmarkPage",
      "setRoutes",
      "getSettings",
      "getFitToClass",
    ]),
    setActivePageForRoute(page) {
      if (page < 0) {
        console.warn("Page out of bounds. Redirecting to 0.");
        return this.routeToPage(0);
      } else if (page > this.book.maxPage) {
        console.warn(
          `Page out of bounds. Redirecting to ${this.book.maxPage}.`
        );
        return this.routeToPage(this.book.maxPage);
      }
      this.activePage = page;
      this.setRoutesAndBookmarkPage(+this.$route.params.page);
      window.scrollTo(0, 0);
    },
  },
};
</script>

/* Inherits v-window styles from books-window */
<style scoped lang="scss">
.windowItem {
  /* prevents inline images from padding and producing scroll bars */
  font-size: 0;
}
</style>

<template>
  <v-window show-arrows :model-value="storePage" :reverse="readInReverse">
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
      :eager="page >= storePage - 1 && page <= storePage + 2"
      :model-value="page"
      :transition="true"
    >
      <BookPage
        v-if="!readInReverse || (secondPage && page < book.maxPage)"
        :book="book"
        :page="readInReverse ? page + 1 : page"
      />
      <BookPage
        v-if="readInReverse || (secondPage && page < book.maxPage)"
        :book="book"
        :page="readInReverse ? page : page + 1"
      />
    </v-window-item>
  </v-window>
</template>

<script>
// 6 is the magic number to avoid disappearing items at the midpoint.
import _ from "lodash";
import { mapActions, mapGetters, mapState } from "pinia";

import BookPage from "@/components/reader/page.vue";
import PageChangeLink from "@/components/reader/page-change-link.vue";
import { useReaderStore } from "@/stores/reader";

export default {
  name: "PagesWindowHorizontal",
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
      activePage: 0,
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
    twoPages() {
      return this.settings.twoPages;
    },
    readInReverse() {
      return this.settings.readInReverse;
    },
    secondPage() {
      return this.settings.twoPages && !this.isOnCoverPage;
    },
    pages() {
      const len = this.book?.maxPage + 1 ?? 0;
      return _.range(0, len);
    },
  },
  watch: {
    twoPages() {
      this.setActivePage(this.storePage);
    },
    storePage(to) {
      if (this.book.pk === this.storePk) {
        this.activePage = to;
      }
    },
    prevBook(to) {
      if (this.book.pk === to.pk) {
        this.activePage = this.book.maxPage;
      }
    },
    nextBook(to) {
      if (this.book.pk === to.pk) {
        this.activePage = 0;
      }
    },
  },
  created() {
    if (this.book.pk === this.storePk) {
      // Active Book
      this.activePage = +this.$route.params.page;
    } else if (this.book.pk === this.prevBook.pk) {
      // Prev Book
      this.activePage = this.book.maxPage;
    } else {
      // Must be next book
      this.activePage = 0;
    }
  },
  methods: {
    ...mapActions(useReaderStore, [
      "getSettings",
      "setBookChangeFlag",
      "setActivePage",
    ]),
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

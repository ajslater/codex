<template>
  <v-window
    id="booksWindow"
    direction="vertical"
    :model-value="currentBookPk"
    :reverse="isBTT"
    show-arrows
    @click="toggleToolbars"
  >
    <template #prev>
      <BookChangeActivator v-if="bookChangePrev" direction="prev" />
      <PageChangeLink v-else direction="prev" />
    </template>
    <template #next>
      <BookChangeActivator v-if="bookChangeNext" direction="next" />
      <PageChangeLink v-else direction="next" />
    </template>
    <v-window-item
      v-for="book of books"
      :key="`c/${book.pk}`"
      class="windowItem"
      disabled
      :eager="eager(book.pk)"
      :value="book.pk"
      :transition="true"
    >
      <Pager :book="book" @click="click" />
    </v-window-item>
  </v-window>
</template>

<script>
import { mapActions, mapGetters, mapState } from "pinia";

import BookChangeActivator from "@/components/reader/book-change-activator.vue";
import PageChangeLink from "@/components/reader/page-change-link.vue";
import Pager from "@/components/reader/pager/pager.vue";
import { useReaderStore } from "@/stores/reader";

export default {
  name: "BooksWindow",
  components: {
    BookChangeActivator,
    PageChangeLink,
    Pager,
  },
  computed: {
    ...mapGetters(useReaderStore, ["isBTT"]),
    ...mapState(useReaderStore, {
      books: (state) =>
        [state.books.prev, state.books.current, state.books.next].filter(
          Boolean,
        ),
      bookChange: (state) => state.bookChange,
      currentBookPk: (state) => state.books?.current?.pk || 0,
      bookRoutes: (state) => state.routes.books,
    }),
    bookChangePrev() {
      return this.bookChangeShow("prev");
    },
    bookChangeNext() {
      return this.bookChangeShow("next");
    },
  },
  watch: {
    $route(to, from) {
      if (!from || !from.params || +to.params.pk !== +from.params.pk) {
        this.loadBooks({ params: to.params });
      }
    },
  },
  beforeMount() {
    this.setBookChangeFlag();
    this.loadBooks({});
  },
  methods: {
    ...mapActions(useReaderStore, [
      "bookChangeShow",
      "loadBooks",
      "setBookChangeFlag",
      "toggleToolbars",
    ]),
    click() {
      this.toggleToolbars();
      this.setBookChangeFlag();
    },
    eager(pk) {
      return (
        this.bookChange &&
        this.bookRoutes[this.bookChange] &&
        this.bookRoutes[this.bookChange].pk === pk
      );
    },
  },
};
</script>

<style scoped lang="scss">
// These window controls also cacade into the pages-window
:deep(.windowItem) {
  /* keeps clickable area full screen when image is small */
  min-height: 100vh;
  text-align: center;
}

:deep(.v-window__controls) {
  position: fixed;
  top: 48px;
  height: calc(100vh - 96px);
  padding: 0;
}
</style>

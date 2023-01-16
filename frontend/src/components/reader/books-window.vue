<template>
  <v-window
    id="booksWindow"
    direction="vertical"
    :model-value="activeBookPk"
    show-arrows
    @click="click"
  >
    <template #prev>
      <BookChangeActivator direction="prev" />
    </template>
    <template #next>
      <BookChangeActivator direction="next" />
    </template>
    <v-window-item
      v-for="[pk, book] of books"
      :key="`c/${pk}`"
      class="windowItem"
      disabled
      :eager="eager(pk)"
      :value="pk"
      :transition="true"
    >
      <PagesWindow :book="book" @click="click" />
    </v-window-item>
  </v-window>
</template>

<script>
import { mapActions, mapState } from "pinia";

import BookChangeActivator from "@/components/reader/book-change-activator.vue";
import PagesWindow from "@/components/reader/pages-window.vue";
import { useReaderStore } from "@/stores/reader";

export default {
  name: "BooksWindow",
  components: {
    BookChangeActivator,
    PagesWindow,
  },
  emits: ["click"],
  computed: {
    ...mapState(useReaderStore, {
      books: (state) => state.books,
      bookChange: (state) => state.bookChange,
      activeBookPk: (state) => state.pk,
      bookRoutes: (state) => state.routes.books,
    }),
  },
  watch: {
    $route(to, from) {
      if (!from || !from.params || +to.params.pk !== +from.params.pk) {
        this.loadBooks(to.params);
      }
    },
  },
  beforeMount() {
    this.setBookChangeFlag();
  },
  created() {
    this.loadBooks(this.$route.params);
  },
  methods: {
    ...mapActions(useReaderStore, ["setBookChangeFlag", "loadBooks"]),
    click() {
      this.setBookChangeFlag();
      this.$emit("click");
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

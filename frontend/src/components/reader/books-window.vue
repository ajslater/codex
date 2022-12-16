<template>
  <v-window
    id="booksWindow"
    direction="vertical"
    :model-value="activeBookPk"
    show-arrows
    @click="click"
  >
    <template #prev>
      <BookChangeDrawer direction="prev" />
    </template>
    <template #next>
      <BookChangeDrawer direction="next" />
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

import BookChangeDrawer from "@/components/reader/book-change-drawer.vue";
import { useReaderStore } from "@/stores/reader";

export default {
  name: "BooksWindow",
  components: {
    BookChangeDrawer,
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

<!-- eslint-disable-next-line vue-scoped-css/enforce-style-type -->
<style lang="scss">
#booksWindow .windowItem {
  /* keeps clickable area full screen when image is small */
  min-height: 100vh;
  text-align: center;
}
#booksWindow .v-window__controls {
  position: fixed;
  top: 48px;
  height: calc(100vh - 96px);
  padding: 0;
}
</style>

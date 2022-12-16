<template>
  <v-window
    id="booksWindow"
    direction="vertical"
    :model-value="activeBookPk"
    show-arrows
    @click="click"
  >
    <template #prev>
      <div
        v-if="showBookPrev"
        class="upArrow bookChangeColumn"
        @click.stop="setBookChangeFlag('prev')"
      >
        <BookChangeDrawer direction="prev" />
      </div>
    </template>
    <template #next>
      <div
        v-if="showBookNext"
        class="downArrow bookChangeColumn"
        @click.stop="setBookChangeFlag('next')"
      >
        <BookChangeDrawer direction="next" />
      </div>
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
import { mapActions, mapGetters, mapState } from "pinia";

import BookChangeDrawer from "@/components/reader/book-change-drawer.vue";
import { useReaderStore } from "@/stores/reader";

export default {
  name: "BooksWindow",
  components: {
    BookChangeDrawer,
  },
  emits: ["click"],
  computed: {
    ...mapGetters(useReaderStore, ["activeBook"]),
    ...mapState(useReaderStore, {
      books: (state) => state.books,
      bookChange: (state) => state.bookChange,
      activeBookPk: (state) => state.pk,
      bookRoutes: (state) => state.routes.books,
    }),
    maxPage() {
      return this.activeBook ? this.activeBook.maxPage : 0;
    },
    showBookPrev() {
      return +this.$route.params.page === 0;
    },
    showBookNext() {
      return +this.$route.params.page === this.maxPage;
      // TODO twopages
    },
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
.windowItem {
  /* keeps clickable area full screen when image is small */
  min-height: 100vh;
  text-align: center;
}
.bookChangeColumn {
  position: absolute;
  height: 100%;
  width: 33vw;
  z-index: 15 !important;
}
#booksWindow .upArrow {
  cursor: n-resize;
}
#booksWindow .downArrow {
  cursor: s-resize;
  right: 0 !important;
}
</style>
<!-- eslint-disable-next-line vue-scoped-css/enforce-style-type -->
<style lang="scss">
#booksWindow .v-window__controls {
  position: fixed;
  top: 48px;
  height: calc(100vh - 96px);
  padding: 0;
}
</style>

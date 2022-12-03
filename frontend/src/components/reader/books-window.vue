<template>
  <v-window
    id="booksWindow"
    ref="booksWindow"
    :model-value="activeBookPk"
    vertical
    touchless
  >
    <ChangeBookDrawer direction="prev" />
    <v-window-item
      v-for="[pk, book] of books"
      :key="`c/${pk}`"
      class="windowItem"
      disabled
      :eager="eager(pk)"
      :model-value="pk"
    >
      <PagesWindow :book="book" @click="click" />
    </v-window-item>
    <ChangeBookDrawer direction="next" />
  </v-window>
</template>

<script>
import { mapActions, mapState } from "pinia";

import ChangeBookDrawer from "@/components/reader/change-book-drawer.vue";
import { useReaderStore } from "@/stores/reader";

export default {
  name: "BooksWindow",
  components: {
    ChangeBookDrawer,
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
  mounted() {
    const windowContainer = this.$refs.booksWindow.$el.children[0];
    windowContainer.addEventListener("click", this.click);
  },
  unmounted() {
    const windowContainer = this.$refs.booksWindow.$el.children[0];
    windowContainer.removeEventListener("click", this.click);
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
</style>
<!-- eslint-disable-next-line vue-scoped-css/enforce-style-type -->
<style lang="scss">
#booksWindow .v-window__prev,
#booksWindow .v-window__next {
  position: fixed;
  top: 48px;
  width: 33vw;
  height: calc(100vh - 96px);
  border-radius: 0;
  margin: 0;
  opacity: 0;
  z-index: 10;
}
#booksWindow .v-window__prev {
  cursor: w-resize;
}
#booksWindow .v-window__next {
  cursor: e-resize;
}
</style>

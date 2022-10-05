<template>
  <v-window
    id="booksWindow"
    ref="booksWindow"
    :value="windowBook"
    vertical
    touchless
  >
    <ChangeBookDrawer direction="prev" />
    <v-window-item
      v-for="pk of books"
      :key="`c/${pk}`"
      class="windowItem"
      disabled
      :eager="eager(pk)"
      :value="pk"
    >
      <PagesWindow :pk="pk" @click="click" />
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
  data() {
    return {
      windowBook: +this.$route.params.pk,
    };
  },
  computed: {
    ...mapState(useReaderStore, {
      books: function (state) {
        const res = [];
        const routes = state.routes;
        const series = state.comic.series;
        if (routes && !routes.prev && series && series.prev) {
          res.push(series.prev.pk);
        }
        if (!res.includes(+this.$route.params.pk)) {
          res.push(+this.$route.params.pk);
        }
        if (
          routes &&
          !routes.next &&
          series &&
          series.next &&
          !res.includes(series.next.pk)
        ) {
          res.push(series.next.pk);
        }
        return res;
      },
      bookChange: (state) => state.bookChange,
      series: (state) => state.comic.series,
    }),
  },
  watch: {
    $route(to, from) {
      if (!from || !from.params || +to.params.pk !== +from.params.pk) {
        this.loadBook();
        this.windowBook = +to.params.pk;
      }
    },
  },
  mounted() {
    const windowContainer = this.$refs.booksWindow.$el.children[0];
    windowContainer.addEventListener("click", this.click);
  },
  unmounted() {
    const windowContainer = this.$refs.booksWindow.$el.children[0];
    windowContainer.removeEventListener("click", this.click);
  },
  methods: {
    ...mapActions(useReaderStore, [
      "routeToDirection",
      "setBookChangeFlag",
      "loadBook",
    ]),
    click() {
      this.setBookChangeFlag();
      this.$emit("click");
    },
    eager(pk) {
      return (
        (this.series.next &&
          this.series.next.pk === pk &&
          this.bookChange === "next") ||
        (this.series.prev &&
          this.series.prev.pk === pk &&
          this.bookChange === "prev")
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

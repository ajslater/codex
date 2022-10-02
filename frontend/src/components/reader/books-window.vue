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
      v-for="pk in books"
      :key="`c/${pk}`"
      class="windowItem"
      disabled
      :eager="
        (routes.prevBook &&
          routes.prevBook.pk === pk &&
          bookChange === 'prev') ||
        (routes.nextBook && routes.nextBook === pk && bookChange === 'next')
      "
      :value="pk"
    >
      <PagesWindow
        :pk="pk"
        :initial-page="
          routes.prevBook && pk === routes.prevBook.pk
            ? routes.prevBook.page
            : 0
        "
      />
    </v-window-item>
    <ChangeBookDrawer direction="next" />
  </v-window>
</template>

<script>
import { mapActions, mapState } from "pinia";

import { getComicPageSource } from "@/api/v3/reader";
import ChangeBookDrawer from "@/components/reader/change-book-drawer.vue";
import { useReaderStore } from "@/stores/reader";

const PREFETCH_LINK = { rel: "prefetch", as: "image" };

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
  head() {
    const links = [];
    if (this.nextSrc) {
      links.push({ ...PREFETCH_LINK, href: this.nextSrc });
    }
    if (this.prevSrc) {
      links.push({ ...PREFETCH_LINK, href: this.prevSrc });
    }
    if (links.length > 0) {
      return { link: links };
    }
  },
  computed: {
    ...mapState(useReaderStore, {
      books: function (state) {
        const res = [];
        const routes = state.routes;
        if (!routes.prev && routes.prevBook) {
          res.push(+routes.prevBook.pk);
        }
        if (!res.includes(+this.$route.params.pk)) {
          res.push(+this.$route.params.pk);
        }
        if (
          !routes.next &&
          routes.nextBook &&
          !res.includes(+routes.nextBook.pk)
        ) {
          res.push(+routes.nextBook.pk);
        }
        return res;
      },
      routes: (state) => state.routes,
      bookChange: (state) => state.bookChange,
      nextSrc(state) {
        const routes = state.routes;
        if (!routes.next && routes.nextBook) {
          return getComicPageSource(routes.nextBook, state.timestamp);
        }
      },
      prevSrc(state) {
        const routes = state.routes;
        if (!routes.prev && routes.prevBook) {
          return getComicPageSource(routes.prevBook, state.timestamp);
        }
      },
      comicLoaded: (state) => state.comicLoaded,
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
        (this.bookChange === "next " && this.routes.nextBook.pk === pk) ||
        (this.bookChange === "prev " && this.routes.prevBook.pk === pk)
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

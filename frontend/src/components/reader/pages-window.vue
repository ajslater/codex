<template>
  <v-window
    id="pagesWindow"
    ref="pagesWindow"
    v-model="windowPage"
    show-arrows
    :vertical="vertical"
    @change="change"
  >
    <template #prev="{ on, attrs }">
      <div class="navColumn" v-bind="attrs" v-on="on"></div>
    </template>
    <template #next="{ on, attrs }">
      <div class="navColumn" v-bind="attrs" v-on="on"></div>
    </template>
    <v-window-item
      v-for="(_, page) in maxPage + 1"
      :key="`c/${pk}/${page}`"
      class="windowItem"
    >
      <PDFPage v-if="isPDF" :source="getSrc(page)" />
      <img
        v-else
        class="page"
        :class="fitToClass"
        :src="getSrc(page)"
        :alt="`Page ${page}`"
      />
      <PDFPage
        v-if="secondPage && isPDF"
        :source="getSrc(page + 1)"
        :classes="fitToClass"
      />
      <img
        v-else-if="secondPage"
        class="page"
        :class="fitToClass"
        :src="getSrc(page + 1)"
        :alt="`Page ${page + 1}`"
      />
    </v-window-item>
  </v-window>
</template>

<script>
import { mapActions, mapGetters, mapState } from "pinia";

import { getComicPageSource } from "@/api/v3/reader";
const PDFPage = () => import("@/components/reader/pdf.vue");
import { useReaderStore } from "@/stores/reader";

export default {
  name: "PagesWindow",
  components: {
    PDFPage,
  },
  data() {
    return {
      windowPage: 0,
    };
  },
  head() {
    if (this.prefetchHref) {
      return {
        lnk: [{ rel: "prefetch", as: "image", href: this.prefetchHref }],
      };
    }
  },
  computed: {
    ...mapGetters(useReaderStore, ["computedSettings", "fitToClass"]),
    ...mapState(useReaderStore, {
      maxPage: (state) => state.comic.maxPage || 0,
      isPDF: (state) => state.comic.fileFormat === "pdf",
      routes: (state) => state.routes,
      timestamp: (state) => state.timestamp,
      secondPage(state) {
        return (
          state.computedSettings.twoPages &&
          +this.windowPage + 1 <= state.comic.maxPage
        );
      },
      vertical: (state) => state.bookChange !== undefined,
      prefetchHref(state) {
        if (!state.routes.next) {
          return;
        }
        return getComicPageSource(state.routes.next, state.timestamp);
      },
    }),
    pk() {
      return this.$route.params.pk;
    },
  },
  watch: {
    $route: function () {
      this.setPage();
    },
  },
  created() {
    this.setPage();
  },
  mounted() {
    const windowContainer = this.$refs.pagesWindow.$el.children[0];
    windowContainer.addEventListener("click", this.click);
  },
  unmounted() {
    const windowContainer = this.$refs.pagesWindow.$el.children[0];
    windowContainer.removeEventListener("click", this.click);
  },
  methods: {
    ...mapActions(useReaderStore, ["routeToPage", "setBookChangeFlag"]),
    getSrc(page) {
      const routeParams = { ...this.$router.currentRoute.params, page };
      return getComicPageSource(routeParams, this.timestamp);
    },
    setPage: function () {
      const params = this.$router.currentRoute.params;
      const pk = +params.pk;
      if (pk === this.routes.prevBook || pk === this.routes.nextBook) {
        // Hacky way to avoid using a separate v-window for books.
        // Wait until the new comic has loaded to set the window page.
        setTimeout(() => {
          this.setPage(pk);
        }, 100);
      } else {
        this.windowPage = +params.page;
      }
    },
    change(page) {
      if (page === undefined || page < 0 || page > this.maxPage) {
        return;
      }
      this.routeToPage(page);
    },
    click(event) {
      const navColumnWidth = window.innerWidth / 3;
      if (event.x < navColumnWidth) {
        this.setBookChangeFlag("prev");
      } else if (event.x > window.innerWidth - navColumnWidth) {
        this.setBookChangeFlag("next");
      } else {
        this.setBookChangeFlag();
        this.$emit("click");
      }
    },
  },
};
</script>

<style scoped lang="scss">
.navColumn {
  width: 100%;
  height: 100%;
}
.windowItem {
  /* keeps clickable area full screen when image is small */
  min-height: 100vh;
  text-align: center;
}
.page {
}
.fitToScreen,
.fitToScreenTwo {
  max-height: 100vh;
}
.fitToScreen {
  max-width: 100vw;
}
.fitToHeight,
.fitToHeightTwo {
  height: 100vh;
}
.fitToWidth {
  width: 100vw;
}
.fitToWidthTwo {
  width: 50vw;
}
.fitToScreenTwo {
  max-width: 50vw;
}
.fitToOrig,
.fitToOrigTwo {
  object-fit: none;
}
</style>
<!-- eslint-disable-next-line vue-scoped-css/enforce-style-type -->
<style lang="scss">
#pagesWindow .v-window__prev,
#pagesWindow .v-window__next {
  position: fixed;
  top: 48px;
  width: 33vw;
  height: calc(100vh - 96px);
  border-radius: 0;
  opacity: 0;
}
#pagesWindow .v-window__prev {
  cursor: w-resize;
}
#pagesWindow .v-window__next {
  cursor: e-resize;
}
</style>

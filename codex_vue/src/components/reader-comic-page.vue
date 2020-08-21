<template>
  <img
    v-if="displayPage"
    class="page"
    :class="fitToClass"
    :src="src"
    :alt="alt"
  />
</template>

<script>
import { mapGetters, mapState } from "vuex";

import { getComicPageSource } from "@/api/reader";

export default {
  name: "ReaderComicPage",
  props: {
    page: {
      type: Number,
      required: true,
      default: 0,
    },
  },
  computed: {
    ...mapState("reader", {
      pk: (state) => state.routes.current.pk,
      basePageNumber: (state) => state.routes.current.pageNumber,
      maxPage: (state) => state.maxPage,
    }),
    ...mapGetters("reader", ["computedSettings"]),
    pageNumber() {
      return this.basePageNumber + this.page;
    },
    displayPage() {
      return (
        this.pageNumber <= this.maxPage &&
        this.pageNumber >= 0 &&
        (this.page === 0 || this.computedSettings.twoPages)
      );
    },
    src() {
      return getComicPageSource({
        pk: this.pk,
        pageNumber: this.pageNumber,
      });
    },
    alt() {
      return `Page ${this.pageNumber}`;
    },
    fitToClass() {
      let cls = "";
      const fitTo = this.computedSettings.fitTo;
      if (fitTo) {
        cls = "fitTo";
        cls += fitTo.charAt(0).toUpperCase();
        cls += fitTo.slice(1).toLowerCase();
        if (this.computedSettings.twoPages) {
          cls += "Two";
        }
      }
      return cls;
    },
  },
};
</script>

<style scoped lang="scss">
.page {
  display: inline-block;
}
.fitToHeight,
.fitToHeightTwo {
  max-height: 100vh;
}
.fitToWidth {
  max-width: 100vw;
}
.fitToWidthTwo {
  max-width: 50vw;
}
.fitToOriginal,
.fitToOriginalTwo {
}
</style>

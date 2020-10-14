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

import { getComicPageSource } from "@/api/v2/comic";

export default {
  name: "ReaderComicPage",
  props: {
    pageIncrement: {
      type: Number,
      required: true,
      default: 0,
    },
  },
  computed: {
    ...mapState("reader", {
      pk: (state) => state.routes.current.pk,
      page: function (state) {
        return state.routes.current.page + this.pageIncrement;
      },
      maxPage: (state) => state.maxPage,
    }),
    ...mapGetters("reader", ["computedSettings"]),
    displayPage() {
      return (
        this.page <= this.maxPage &&
        this.page >= 0 &&
        (this.page === 0 || this.computedSettings.twoPages)
      );
    },
    src() {
      return getComicPageSource({
        pk: this.pk,
        page: this.page,
      });
    },
    alt() {
      return `Page ${this.page}`;
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
  flex: 0 0 auto;
  /* align-self fixes mobile safari stretching the image weirdly */
  align-self: flex-start;
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
</style>

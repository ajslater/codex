<template>
  <PaginationNavButton
    icon
    variant="plain"
    :disabled="disabled"
    :title="title"
    :to="toRoute"
  >
    <v-icon>
      {{ icon }}
    </v-icon>
  </PaginationNavButton>
</template>

<script>
import { mdiBookArrowDown, mdiBookArrowUp } from "@mdi/js";
import { mapState } from "pinia";

import PaginationNavButton from "@/components/pagination-nav-button.vue";
import { useReaderStore } from "@/stores/reader";
export default {
  name: "ReaderBookChangeNavButton",
  components: {
    PaginationNavButton,
  },
  props: {
    direction: {
      type: String,
      required: true,
    },
  },
  computed: {
    ...mapState(useReaderStore, {
      books: (state) => state.routes.books,
    }),
    toRoute() {
      const params = this.books[this.direction];
      if (params) {
        return { params };
      }
      return "";
    },
    title() {
      const prefix = this.direction === "prev" ? "Previous" : "Next";
      return prefix + " Book";
    },
    icon() {
      return this.direction === "prev" ? mdiBookArrowUp : mdiBookArrowDown;
    },
    disabled() {
      return !this.toRoute;
    },
  },
};
</script>

<template>
  <PaginationNavButton
    v-if="toRoute"
    :class="classes"
    :icon="icon"
    variant="plain"
    :title="title"
    :to="toRoute"
  />
</template>

<script>
import { mapActions, mapState } from "pinia";

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
    ...mapState(useReaderStore, ["isBTT", "routes"]),
    toRoute() {
      // Delegate the route shape to the store's toRoute so the reader's
      // page-in-query convention lives in one place. Keep "" (not {}) when
      // there's no adjacent book so the v-if hides the button.
      const params = this.routes?.books?.[this.direction];
      return params ? this.makeReaderRoute(params) : "";
    },
    title() {
      const prefix = this.direction === "prev" ? "Previous" : "Next";
      return prefix + " Book";
    },
    icon() {
      return this.bookChangeIcon(this.direction);
    },
    classes() {
      return {
        bookChangeNavButtonLeft: this.direction === "prev",
        bookChangeNavButtonRight: this.direction === "next",
      };
    },
  },
  methods: {
    ...mapActions(useReaderStore, ["bookChangeIcon"]),
    ...mapActions(useReaderStore, { makeReaderRoute: "toRoute" }),
  },
};
</script>
<style scoped lang="scss">
.bookChangeNavButtonLeft {
  padding-left: max(15px, calc(env(safe-area-inset-left) / 3));
}

.bookChangeNavButtonRight {
  padding-right: max(15px, calc(env(safe-area-inset-right) / 3));
}
</style>

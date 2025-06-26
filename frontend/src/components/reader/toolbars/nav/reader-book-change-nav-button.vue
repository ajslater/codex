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
import deepClone from "deep-clone";
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
    ...mapState(useReaderStore, ["isBTT"]),
    ...mapState(useReaderStore, {
      toRoute(state) {
        const params = state?.routes?.books[this.direction];
        return params ? { params: deepClone(params) } : "";
      },
    }),
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

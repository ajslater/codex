<template>
  <PaginationNavButton
    :key="isVertical"
    :disabled="disabled"
    class="readerNavButton"
    :class="classes"
    :title="title"
    :to="toRoute"
    @click="onClick"
  >
    {{ value }}
  </PaginationNavButton>
</template>

<script>
import { mapActions, mapState } from "pinia";

import PaginationNavButton from "@/components/pagination-nav-button.vue";
import { useReaderStore } from "@/stores/reader";
export default {
  name: "ReaderNavButton",
  components: {
    PaginationNavButton,
  },
  props: {
    value: {
      type: Number,
      required: true,
    },
    twoPages: {
      type: Boolean,
      default: false,
    },
  },
  computed: {
    ...mapState(useReaderStore, ["isVertical"]),
    ...mapState(useReaderStore, {
      storePage: (state) => state.page,
      toRoute(state) {
        if (!this.isVertical) {
          return {
            params: { pk: state.books.current.pk, page: this.value },
          };
        }
      },
      isBookPrev: (state) => Boolean(state.routes.books.prev),
      isBookNext: (state) => Boolean(state.routes.books.next),
    }),
    classes() {
      return {
        readerNavButtonLeft: !this.isBookPrev && this.value === 0,
        readerNavButtonRight: !this.isBookNext && this.value != 0,
      };
    },
    title() {
      return "Page " + this.value;
    },
    disabled() {
      return (
        this.value === this.storePage ||
        (this.twoPages &&
          Boolean(this.value % 2) &&
          this.value - 1 === this.storePage)
      );
    },
  },
  methods: {
    ...mapActions(useReaderStore, ["setActivePage"]),
    onClick() {
      if (this.isVertical) {
        this.setActivePage(this.value, true);
      }
    },
  },
};
</script>
<style scoped lang="scss">
.readerNavButton {
  padding-left: 15px;
  padding-right: 15px;
}
.readerNavButtonLeft {
  padding-left: max(15px, calc(env(safe-area-inset-left) / 3)) !important;
}
.readerNavButtonRight {
  padding-right: max(15px, calc(env(safe-area-inset-right) / 3)) !important;
}
</style>

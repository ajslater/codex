<template>
  <PaginationNavButton
    :key="isVertical || toRoute"
    :disabled="disabled"
    :title="title"
    :to="toRoute"
    @click="onClick"
  >
    {{ value }}
  </PaginationNavButton>
</template>

<script>
import { mapActions, mapGetters, mapState } from "pinia";

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
    ...mapGetters(useReaderStore, ["isVertical"]),
    ...mapState(useReaderStore, {
      storePage: (state) => state.page,
      toRoute(state) {
        if (!this.isVertical) {
          return {
            params: { pk: state.books.current.pk, page: this.value },
          };
        }
      },
    }),
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

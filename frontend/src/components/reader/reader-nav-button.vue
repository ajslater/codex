<template>
  <PaginationNavButton
    v-if="vertical"
    :disabled="disabled"
    :title="title"
    @click="onClick"
  >
    {{ value }}
  </PaginationNavButton>
  <PaginationNavButton v-else :disabled="disabled" :title="title" :to="toRoute">
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
    ...mapState(useReaderStore, {
      storePage: (state) => state.page,
      vertical: (state) => state.activeSettings?.vertical,
      toRoute(state) {
        return {
          params: { pk: state.pk, page: this.value },
        };
      },
    }),
    title() {
      return "to page " + this.value;
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
    ...mapActions(useReaderStore, ["setPage"]),
    onClick() {
      this.setPage(this.value, true);
    },
  },
};
</script>

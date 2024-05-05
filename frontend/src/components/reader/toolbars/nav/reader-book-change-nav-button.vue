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
import { mapActions, mapGetters, mapState } from "pinia";

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
    ...mapGetters(useReaderStore, ["isBTT"]),
    ...mapState(useReaderStore, {
      toRoute(state) {
        const params = state?.routes?.books[this.direction];
        return params ? { params: { ...params } } : "";
      },
    }),
    title() {
      const prefix = this.direction === "prev" ? "Previous" : "Next";
      return prefix + " Book";
    },
    icon() {
      return this.bookChangeIcon(this.direction);
    },
    disabled() {
      return !this.toRoute;
    },
  },
  methods: {
    ...mapActions(useReaderStore, ["bookChangeIcon"]),
  },
};
</script>

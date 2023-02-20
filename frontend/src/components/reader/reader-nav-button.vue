<template>
  <PaginationNavButton :disabled="disabled" :title="title" :to="toRoute">
    {{ value }}
  </PaginationNavButton>
</template>

<script>
import PaginationNavButton from "@/components/pagination-nav-button.vue";
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
    toRoute() {
      return {
        params: { ...this.$route.params, page: this.value },
      };
    },
    title() {
      return "to page " + this.value;
    },
    disabled() {
      return (
        this.value === +this.$route.params.page ||
        (this.twoPages &&
          Boolean(this.value % 2) &&
          this.value - 1 === +this.$route.params.page)
      );
    },
  },
};
</script>

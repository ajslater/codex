<template>
  <v-btn class="readerNavButton" :disabled="disabled" :to="toRoute" height="48">
    {{ value }}
  </v-btn>
</template>

<script>
export default {
  name: "ReaderNavButton",
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
    disabled() {
      return (
        this.value === +this.$route.params.page ||
        (this.twoPages &&
          this.value % 2 &&
          this.value - 1 === +this.$route.params.page)
      );
    },
  },
};
</script>

<style scoped lang="scss">
.readerNavButton {
  margin-inline-start: 0 !important;
  margin-inline-end: 0 !important;
}
</style>

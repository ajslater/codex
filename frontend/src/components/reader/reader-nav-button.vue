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
    toRoute: function () {
      const params = { ...this.$route.params };
      params.page = this.value;
      return {
        name: this.$route.name,
        params: params,
      };
    },
    disabled: function () {
      const endPages = [this.value];
      if (this.twoPages && this.value % 2) {
        endPages.push(this.value - 1);
      }
      return endPages.includes(+this.$route.params.page);
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

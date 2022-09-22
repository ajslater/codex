<template>
  <v-btn
    class="readerNavButton"
    :disabled="disabled"
    :to="toRoute"
    ripple
    large
  >
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
      return this.$route.params.page === this.value;
    },
  },
};
</script>

<style scoped lang="scss">
.readerNavButton {
  z-index: -1;
}
</style>

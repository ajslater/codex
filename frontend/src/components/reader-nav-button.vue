<template>
  <v-btn
    :disabled="pageNumber === value"
    :to="{ name: 'reader', params: { pk, pageNumber: value } }"
    ripple
    large
  >
    {{ value }}
  </v-btn>
</template>

<script>
import { mapState } from "vuex";

export default {
  name: "ReaderNavButton",
  props: {
    value: {
      type: Number,
      required: true,
      default: 0,
    },
  },
  computed: {
    ...mapState("reader", {
      pk: (state) => state.routes.current.pk,
      pageNumber: (state) => state.routes.current.pageNumber,
    }),
  },
};
</script>

<style scoped lang="scss"></style>

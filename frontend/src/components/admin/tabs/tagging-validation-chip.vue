<template>
  <v-chip
    :color="result.ok ? 'success' : 'error'"
    :prepend-icon="result.ok ? 'mdi-check-circle' : 'mdi-alert-circle'"
    size="small"
    variant="tonal"
    class="validationChip"
  >
    {{ chipText }}
  </v-chip>
</template>

<script>
export default {
  name: "TaggingValidationChip",
  props: {
    result: {
      type: Object,
      required: true,
    },
  },
  computed: {
    chipText() {
      if (this.result.ok) return "Connected";
      return this.result.error || "Failed";
    },
  },
};
</script>

<style scoped lang="scss">
.validationChip {
  align-self: flex-start;
}
</style>

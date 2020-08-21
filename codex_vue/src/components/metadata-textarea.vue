<template>
  <v-textarea
    v-if="value || show"
    :value="value"
    :label="label"
    :type="type"
    hide-details="auto"
    dense
    readonly
    hide-no-data
    allow-overflow
    rows="1"
    auto-grow
    filled
  />
</template>

<script>
export default {
  name: "MetadataTextArea",
  props: {
    label: {
      type: String,
      required: true,
    },
    value: {
      type: String,
      default: "",
    },
    type: {
      type: String,
      default: "text",
    },
    show: {
      type: Boolean,
      default: false,
    },
  },
};
</script>

<style scoped lang="scss"></style>

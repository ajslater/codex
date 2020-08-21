<template>
  <v-text-field
    v-if="value || show"
    :value="value"
    :label="label"
    :type="type"
    hide-details="auto"
    dense
    readonly
    filled
  />
</template>

<script>
export default {
  name: "MetadataTextField",
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

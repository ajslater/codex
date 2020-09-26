<template>
  <v-text-field
    v-if="value || show"
    v-model="model"
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
      type: Array,
      default: null,
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
  data() {
    return {
      model: this.value,
    };
  },
};
</script>

<style scoped lang="scss"></style>

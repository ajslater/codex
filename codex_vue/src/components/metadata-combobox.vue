<template>
  <v-combobox
    v-if="model || show"
    :value="model"
    :items="[{ value: model, text: model }]"
    :label="label"
    hide-details="auto"
    dense
    readonly
    filled
  />
</template>

<script>
export default {
  name: "MetadataCombobox",
  props: {
    label: {
      type: String,
      default: undefined,
    },
    model: {
      type: String,
      default: "",
    },
    show: {
      type: Boolean,
      default: false,
    },
  },
};
</script>

<style scoped lang="scss"></style>

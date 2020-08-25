<template>
  <v-combobox
    v-if="(tags && tags.length > 0) || show"
    item-value="pk"
    item-text="name"
    :items="tags"
    :value="tags"
    multiple
    :label="label"
    hide-details="auto"
    dense
    chips
    small-chips
    deletable-chips
    readonly
    filled
  />
</template>

<script>
export default {
  name: "MetadataTags",
  props: {
    label: {
      type: String,
      required: true,
    },
    tags: {
      type: Array,
      required: true,
    },
    show: {
      type: Boolean,
      default: false,
    },
  },
  computed: {},
};
</script>

<style scoped lang="scss"></style>

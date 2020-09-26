<template>
  <v-combobox
    v-if="(items && items.length > 0) || show"
    v-model="model"
    :items="items"
    :label="label"
    multiple
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
    items: {
      type: Array,
      default: new Array(),
    },
    show: {
      type: Boolean,
      default: false,
    },
  },
  data() {
    return {
      model: null,
    };
  },
  created: function () {
    this.model = this.items;
  },
};
</script>

<style scoped lang="scss"></style>

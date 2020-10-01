<template>
  <v-combobox
    v-if="(model && model.length > 0) || show"
    v-model="model"
    :items="computedItems"
    item-value="pk"
    item-text="name"
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
import { computedItems } from "@/components/metadata-computed-items";

export default {
  name: "MetadataTags",
  props: {
    label: {
      type: String,
      required: true,
    },
    items: {
      type: Array,
      default: null,
    },
    values: {
      type: Array,
      default: null,
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
  computed: {
    computedItems: function () {
      return computedItems(this.values, this.items);
    },
  },
  created: function () {
    // Different than combobox, returns a list of items.
    this.model = computedItems(null, this.values);
  },
};
</script>

<style scoped lang="scss"></style>

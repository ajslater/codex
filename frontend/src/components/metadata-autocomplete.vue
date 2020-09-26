<template>
  <v-autocomplete
    v-if="model || show"
    v-model="model"
    :items="computedItems"
    :label="label"
    hide-details="auto"
    dense
    readonly
    filled
  />
</template>

<script>
import {
  computedItems,
  initialItem,
} from "@/components/metadata-computed-items";

export default {
  name: "MetadataAutocomplete",
  props: {
    label: {
      type: String,
      default: undefined,
    },
    show: {
      type: Boolean,
      default: false,
    },
    items: {
      type: Array,
      default: null,
    },
    values: {
      type: Array,
      default: null,
    },
  },
  data() {
    return {
      model: null,
    };
  },
  computed: {
    // XXX Identical to Combobox
    computedItems: function () {
      return computedItems(this.items, this.values);
    },
  },
  created: function () {
    // XXX Identical to Combobox
    this.model = initialItem(this.computedItems);
  },
};
</script>

<style scoped lang="scss"></style>

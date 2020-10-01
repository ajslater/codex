<template>
  <v-autocomplete
    v-if="model || show"
    v-model="model"
    :items="computedItems"
    item-value="pk"
    item-text="name"
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
  toVuetifyItem,
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
    value: {
      type: [Object, String, Number, Boolean],
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
      return computedItems(this.value, this.items);
    },
  },
  created: function () {
    // XXX Identical to Combobox
    this.model = toVuetifyItem(this.value);
  },
};
</script>

<style scoped lang="scss"></style>

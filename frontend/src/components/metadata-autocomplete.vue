<template>
  <v-autocomplete
    v-if="model || show"
    v-model="model"
    :items="vuetifyItems"
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
import { toVuetifyItem, toVuetifyItems } from "@/api/v2/list-items";

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
      default: undefined,
    },
  },
  data() {
    return {
      model: undefined,
    };
  },
  computed: {
    // XXX Identical to Combobox use mixin?
    vuetifyItems: function () {
      return toVuetifyItems(this.value, this.items);
    },
  },
  created: function () {
    // XXX Identical to Combobox
    this.model = toVuetifyItem(this.value);
  },
};
</script>

<style scoped lang="scss"></style>

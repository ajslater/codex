<template>
  <v-combobox
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
  name: "MetadataCombobox",
  props: {
    label: {
      type: String,
      default: undefined,
    },
    items: {
      type: Array,
      default: null,
    },
    show: {
      type: Boolean,
      default: false,
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
    computedItems: function () {
      return computedItems(this.value, this.items);
    },
  },
  created: function () {
    this.model = toVuetifyItem(this.value);
  },
};
</script>

<style scoped lang="scss"></style>

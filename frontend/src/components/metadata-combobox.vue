<template>
  <v-combobox
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
      default: undefined,
    },
  },
  data() {
    return {
      model: undefined,
    };
  },
  computed: {
    vuetifyItems: function () {
      return toVuetifyItems(this.value, this.items);
    },
  },
  created: function () {
    this.model = toVuetifyItem(this.value);
  },
};
</script>

<style scoped lang="scss"></style>

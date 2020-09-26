<template>
  <v-checkbox
    v-if="model || show"
    v-model="model"
    :indeterminate="indeterminate"
    :label="label"
    hide-details="auto"
    dense
    ripple
    :readonly="readonly"
  />
</template>
<script>
import { initialValue } from "@/components/metadata-computed-items";

export default {
  name: "MetadataCheckbox",
  props: {
    label: {
      type: String,
      required: true,
    },
    values: {
      type: Array,
      default: null,
    },
    readonly: {
      type: Boolean,
      default: false,
    },
    show: {
      type: Boolean,
      defautl: false,
    },
  },
  data() {
    return {
      model: null,
    };
  },
  computed: {
    indeterminate: function () {
      return this.values && this.values.length > 1;
    },
  },
  created: function () {
    this.model = initialValue(this.values);
  },
};
</script>

<style scoped lang="scss"></style>

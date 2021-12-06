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
export default {
  name: "MetadataCheckbox",
  props: {
    label: {
      type: String,
      required: true,
    },
    value: {
      type: Boolean,
      default: null,
    },
    readonly: {
      type: Boolean,
      default: false,
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
    indeterminate: function () {
      return this.value == null;
    },
  },
  created: function () {
    this.model = this.value;
  },
};
</script>

<style scoped lang="scss"></style>

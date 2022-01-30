<template>
  <v-checkbox
    :value="value"
    :indeterminate="indeterminate"
    :label="label"
    hide-details="auto"
    dense
    readonly
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
    },
  },
  computed: {
    indeterminate: function () {
      return this.value == undefined;
    },
  },
};
</script>

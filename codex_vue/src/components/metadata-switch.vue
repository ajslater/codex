<template>
  <v-switch
    v-model="inputVal"
    :label="label"
    hide-details="auto"
    dense
    :readonly="readonly"
  />
</template>

<script>
export default {
  name: "MetadataSwitch",
  props: {
    label: {
      type: String,
      default: undefined,
    },
    value: {
      type: Boolean,
      default: false,
    },
    readonly: {
      type: Boolean,
      default: false,
    },
  },
  computed: {
    inputVal: {
      get() {
        return this.value;
      },
      set(value) {
        console.log(value);
        this.$emit("input", value);
      },
    },
  },
};
</script>

<style scoped lang="scss"></style>

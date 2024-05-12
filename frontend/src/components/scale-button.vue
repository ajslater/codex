<template>
  <v-btn :density="density" :size="size">
    <template v-for="(props, name) in $slots" #[name]="slotData">
      <slot :name="name" :props="props" v-bind="slotData" />
    </template>
  </v-btn>
</template>
<script>
export default {
  name: "ScaleButton",
  props: {
    scale: {
      type: Boolean,
      default: false,
    },
  },
  computed: {
    breakPoint() {
      return this.$vuetify.display.xs;
    },
    density() {
      return this.scale && this.breakPoint ? "compact" : "default";
    },
    size() {
      return this.scale && this.breakPoint ? "small" : "default";
    },
  },
};
</script>

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
      return this.scale && this.$vuetify.display.smAndDown;
    },
    density() {
      return this.breakPoint ? "compact" : "default";
    },
    size() {
      return this.breakPoint ? "small" : "default";
    },
  },
};
</script>

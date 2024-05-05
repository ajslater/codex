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
  computed: {
    breakPoint() {
      return this.$vuetify.display.xs;
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

<template>
  <v-btn :density="density">
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
      return this.breakPoint ? "compact" : "default";
    },
  },
};
</script>

<template>
  <v-btn variant="plain" density="compact" :class="classes">
    <template v-for="(props, name) in $slots" #[name]="slotData">
      <slot :name="name" :props="props" v-bind="slotData" />
    </template>
  </v-btn>
</template>

<script>
export default {
  name: "PaginationNavButton",
  props: {
    narrow: {
      type: Boolean,
      default: true,
    },
  },
  computed: {
    classes() {
      return {
        narrowButton: this.narrow,
      };
    },
  },
};
</script>

<style scoped lang="scss">
.narrowButton {
  margin-inline-start: 0 !important;
  margin-inline-end: 0 !important;
}
</style>

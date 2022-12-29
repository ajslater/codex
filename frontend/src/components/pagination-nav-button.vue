<template>
  <v-btn class="paginationNavButton" height="100%" v-bind="$attrs">
    <template v-for="(props, name) in $slots" #[name]="slotData">
      <slot :name="name" :props="props" v-bind="slotData" />
    </template>
  </v-btn>
</template>

<script>
export default {
  name: "PaginationNavButton",
};
</script>

<style scoped lang="scss">
.paginationNavButton {
  margin-inline-start: 0 !important;
  margin-inline-end: 0 !important;
}
</style>

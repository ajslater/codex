<template>
  <v-toolbar
    class="paginationToolbar"
    density="compact"
    transform="center bottom"
  >
    <template v-for="(props, name) in $slots" #[name]="slotData">
      <slot :name="name" :props="props" v-bind="slotData" />
    </template>
  </v-toolbar>
</template>

<script>
export default {
  name: "PaginationToolbar",
};
</script>

<style scoped lang="scss">
.paginationToolbar {
  position: fixed !important;
  bottom: env(safe-area-inset-bottom);
  width: 100%;
  padding: 0px;
  z-index: 20;
}
</style>

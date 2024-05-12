<template>
  <v-data-table-virtual
    fixed-header
    item-value="pk"
    :mobile="$vuetify.display.xs"
  >
    <template v-for="(props, name) in $slots" #[name]="slotData">
      <slot :name="name" :props="props" v-bind="slotData" />
    </template>
  </v-data-table-virtual>
</template>
<script>
export default {
  name: "AdminTable",
};
</script>
<style scoped lang="scss">
.adminTable :deep(thead > tr > th, .adminTable tbody > tr:nth-child(even)) {
  background-color: rgb(var(--v-theme-background)) !important;
}
:deep(.adminNoData) {
  padding: 1em;
  text-align: center;
}
</style>

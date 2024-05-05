<template>
  <v-data-table-virtual
    class="adminTable"
    fixed-header
    mobile-breakpoint="md"
    item-value="pk"
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
.adminTable {
  /* Lets data table contents overflow scroll */
  max-width: 100vw;
}
.adminTable :deep(thead > tr > th, .adminTable tbody > tr:nth-child(even)) {
  background-color: rgb(var(--v-theme-background)) !important;
}
:deep(.adminNoData) {
  padding: 1em;
  text-align: center;
}
</style>

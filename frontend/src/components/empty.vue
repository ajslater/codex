<template>
  <v-empty-state class="empty">
    <template v-for="(props, name) in $slots" #[name]="slotData">
      <slot :name="name" :props="props" v-bind="slotData" />
    </template>
  </v-empty-state>
</template>

<script>
export default {
  name: "EmptyState",
};
</script>

<style scoped lang="scss">
.empty {
  color: rgb(var(--v-theme-textDisabled));
}

:deep(.v-empty-state__action-btn) {
  background-color: rgb(var(--v-theme-primary)) !important;
}

:deep(.v-empty-state__action-btn .v-btn__content) {
  color: black;
}
</style>

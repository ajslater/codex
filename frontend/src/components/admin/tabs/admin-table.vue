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
// The rule that previously sat here was malformed: a comma inside
// ``:deep(...)`` rooted under ``.adminTable`` (a class never applied
// to this component or any caller). The selector matched nothing and
// the row striping/header background it claimed to set came entirely
// from the Vuetify ``v-data-table-virtual`` defaults below it.
// Deleted as dead code; the visible result is unchanged.

/* Layered: these rules beat Vuetify's component CSS by position,
 * and lose to a `color`/utility prop, which is the intended order. */
@layer codex-components {
  :deep(.adminNoData) {
    padding: 1em;
    text-align: center;
  }
}
</style>

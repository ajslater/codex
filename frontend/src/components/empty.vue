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
/* Layered: these rules beat Vuetify's component CSS by position,
 * and lose to a `color`/utility prop, which is the intended order. */
@layer codex-components {
  .empty {
    color: rgb(var(--v-theme-text-disabled));
  }

  :deep(.v-empty-state__action-btn .v-btn__content) {
    color: black;
  }
}

/* VEmptyState hands its action button `color: surface-variant`, which
 * arrives as a bg-* utility class — and utilities deliberately outrank
 * codex-components. Beating a utility is what codex-trumps is for.
 * Passing `color="primary"` instead would make Vuetify derive
 * `on-primary` as white and flip the black label above, which is a
 * separate look-at-it decision. */
@layer codex-trumps {
  :deep(.v-empty-state__action-btn) {
    background-color: rgb(var(--v-theme-primary));
  }
}
</style>

<template>
  <v-list-item class="codexListItem" slim compact />
</template>
<script>
export default {
  name: "CodexListItem",
};
</script>
<style scoped lang="scss">
/* Layered: these rules beat Vuetify's component CSS by position,
 * and lose to a `color`/utility prop, which is the intended order. */
@layer codex-components {
  .codexListItem :deep(> .v-list-item__prepend > .v-list-item__spacer) {
    display: none;
  }

  .codexListItem {
    color: rgb(var(--v-theme-text-primary));
  }
}
</style>

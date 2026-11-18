<template>
  <section class="menuSection">
    <header class="menuSectionTitle">{{ title }}</header>
    <slot />
  </section>
</template>

<script>
/*
 * A titled block inside a menu. The shelf menu has one ("Shelves")
 * today; a later section such as "Reading lists" is another
 * ``MenuSection`` beside it.
 */
export default {
  name: "MenuSection",
  props: {
    title: {
      type: String,
      required: true,
    },
  },
};
</script>

<style scoped lang="scss">
.menuSectionTitle {
  padding: 8px 16px 2px;
  font-size: smaller;
  font-weight: bolder;
  color: rgb(var(--v-theme-text-disabled));
}
</style>

<template>
  <section class="menuSection">
    <header class="menuSectionTitle">{{ title }}</header>
    <slot />
  </section>
</template>

<script>
/*
 * A titled block inside a menu. The reading list menu has one
 * ("Reading Lists"); another kind of grouping would be another
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

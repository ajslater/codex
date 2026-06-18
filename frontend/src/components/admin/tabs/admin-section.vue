<!--
  A titled admin block: header (h3 + optional right-aligned actions), an
  optional one-line hint, then its body. The unified replacement for the
  hand-written .adminGroup / .adminGroupHeader / <h3> markup. See DESIGN.md §4.
-->
<template>
  <section class="adminGroup">
    <header v-if="title || $slots.actions" class="adminGroupHeader">
      <h3>{{ title }}</h3>
      <slot name="actions" />
    </header>
    <p v-if="hint || $slots.hint" class="adminHint">
      <slot name="hint">{{ hint }}</slot>
    </p>
    <slot />
  </section>
</template>

<script>
export default {
  name: "AdminSection",
  props: {
    title: { type: String, default: "" },
    hint: { type: String, default: "" },
  },
};
</script>

<style scoped lang="scss">
@use "@/components/admin/tabs/admin-section.scss";
</style>

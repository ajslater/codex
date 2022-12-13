<template>
  <v-select
    v-bind="$attrs"
    :label="selectLabel"
    :aria-label="selectLabel"
    class="toolbarSelect"
    density="compact"
    full-width
    hide-details="auto"
  >
    <template v-for="(props, name) in $slots" #[name]="slotData">
      <slot :name="name" :props="props" v-bind="slotData" />
    </template>
  </v-select>
</template>

<script>
export default {
  name: "ToolbarSelect",
  props: {
    selectLabel: {
      type: String,
      default: "",
    },
  },
};
</script>

<style scoped lang="scss"></style>

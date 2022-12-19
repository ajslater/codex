<template>
  <v-slider
    thumb-size="36"
    class="paginationSlider"
    density="compact"
    hide-details="auto"
    :rounded="true"
    show-ticks="always"
    :step="1"
    thumb-label="always"
    v-bind="$attrs"
  />
</template>

<script>
export default {
  name: "PaginationSlider",
};
</script>

<style scoped lang="scss">
/* Custom slider with a large control. */
:deep(.v-slider-thumb__ripple) {
  width: calc(var(--v-slider-thumb-size) * 1.333);
  height: calc(var(--v-slider-thumb-size) * 1.333);
  top: -6px;
  left: -6px;
}
:deep(.v-slider-thumb__label) {
  bottom: 0px !important;
  transform: translateX(-50%) translateY(125%) !important;
  background-color: transparent;
  color: white;
}
:deep(.v-slider-thumb__label:before) {
  display: none;
}
</style>

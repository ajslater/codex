<template>
  <v-slider
    thumb-size="48"
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
:deep(.v-slider-thumb__label) {
  bottom: 0px !important;
  transform: translateX(-50%) translateY(150%) !important;
  background-color: transparent;
  color: white;
}
:deep(.v-slider-thumb__label:before) {
  display: none;
}
</style>

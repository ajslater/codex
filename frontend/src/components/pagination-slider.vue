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
<style scoped lang="scss"></style>
<!-- eslint-disable-next-line vue-scoped-css/enforce-style-type -->
<style lang="scss">
/* Custom slider with a large control. */
.paginationSlider .v-slider-thumb__label {
  bottom: 0px !important;
  transform: translateX(-50%) translateY(150%) !important;
  background-color: transparent;
  color: white;
}
.paginationSlider .v-slider-thumb__label:before {
  display: none;
}
</style>

<template>
  <v-slider
    class="paginationSlider"
    ticks="always"
    thumb-label="always"
    hide-details="auto"
    dense
    v-bind="$attrs"
    v-on="$listeners"
  />
</template>

<script>
export default {
  name: "PaginationSlider",
};
</script>

<!-- eslint-disable-next-line vue-scoped-css/enforce-style-type -->
<style lang="scss">
/* Custom slider with a large control. */
.paginationSlider .v-slider__thumb {
  height: 48px;
  width: 48px;
  left: -24px;
}
.paginationSlider .v-slider__thumb::before {
  left: -8px;
  top: -8px;
  height: 64px;
  width: 64px;
}
.paginationSlider .v-slider__thumb-label {
  transform: translateY(16px) translateX(-50%) rotate(45deg) !important;
}
</style>

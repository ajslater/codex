<template>
  <v-toolbar v-if="numPages > 1" class="paginationToolbar" dense>
    <BrowserNavButton :back="true" />
    <v-slider
      class="paginationSlider"
      :value="+$route.params.page"
      :min="+1"
      :max="numPages"
      ticks="always"
      thumb-label="always"
      hide-details="auto"
      dense
      @change="routeToPage($event)"
    />
    <BrowserNavButton :back="false" />
  </v-toolbar>
</template>

<script>
import { mapActions, mapState } from "pinia";

import BrowserNavButton from "@/components/browser/nav-button.vue";
import { useBrowserStore } from "@/stores/browser";

export default {
  name: "BrowserNavToolbar",
  components: {
    BrowserNavButton,
  },
  computed: {
    ...mapState(useBrowserStore, {
      numPages: (state) => state.page.numPages,
    }),
  },
  methods: {
    ...mapActions(useBrowserStore, ["routeToPage"]),
  },
};
</script>

<style scoped lang="scss">
.paginationToolbar {
  position: fixed;
  bottom: env(safe-area-inset-bottom);
  width: 100%;
}
</style>

<!-- eslint-disable-next-line vue-scoped-css/enforce-style-type -->
<style lang="scss">
.paginationToolbar > .v-toolbar__content {
  padding: 0px;
}
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

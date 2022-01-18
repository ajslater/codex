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
import { mapState } from "vuex";

import BrowserNavButton from "@/components/browser-nav-button";

export default {
  name: "BrowserPaginationToolbar",
  components: {
    BrowserNavButton,
  },
  computed: {
    ...mapState("browser", {
      numPages: (state) => Number(state.numPages),
    }),
  },
  methods: {
    routeToPage: function (page) {
      this.$store.dispatch("browser/routeToPage", page);
    },
  },
};
</script>

<style scoped lang="scss">
.paginationToolbar {
  position: fixed;
  bottom: 0px;
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

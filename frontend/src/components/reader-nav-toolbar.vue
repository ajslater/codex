<template>
  <v-toolbar
    v-if="maxPage"
    class="readerNavToolbar"
    dense
    transform="center bottom"
  >
    <ReaderNavButton :value="0" />
    <v-slider
      class="readerSlider"
      :value="+$route.params.page"
      :min="+0"
      :max="maxPage"
      ticks="always"
      thumb-label="always"
      hide-details="auto"
      dense
      @change="routeToPage($event)"
    />
    <ReaderNavButton :value="maxPage" />
    <span v-if="seriesPosition" id="seriesPosition">{{ seriesPosition }}</span>
  </v-toolbar>
</template>

<script>
import { mapActions, mapState } from "vuex";

import ReaderNavButton from "@/components/reader-nav-button";

export default {
  name: "ReaderNavToolbar",
  components: {
    ReaderNavButton,
  },
  computed: {
    ...mapState("reader", {
      maxPage: (state) => state.comic.maxPage,
      seriesPosition: function (state) {
        let pos = "";
        if (state.routes.seriesCount > 1) {
          pos = `${state.routes.seriesIndex}/${state.routes.seriesCount}`;
        }
        return pos;
      },
    }),
  },
  methods: {
    ...mapActions("reader", ["routeToPage"]),
  },
};
</script>

<style scoped lang="scss">
.readerNavToolbar {
  position: fixed;
  bottom: 0px;
  width: 100%;
}
#seriesPosition {
  padding-left: 0.5em;
  padding-right: 1em;
  color: darkgray;
}
</style>

<!-- eslint-disable-next-line vue-scoped-css/enforce-style-type -->
<style lang="scss">
/* TOOLBARS */
.readerNavToolbar .v-toolbar__content {
  padding: 0px;
}
/* Custom slider with a large control. */
.readerSlider .v-slider__thumb {
  height: 48px;
  width: 48px;
  left: -24px;
}
.readerSlider .v-slider__thumb::before {
  left: -8px;
  top: -8px;
  height: 64px;
  width: 64px;
}
.readerSlider .v-slider__thumb-label {
  transform: translateY(16px) translateX(-50%) rotate(45deg) !important;
}
</style>

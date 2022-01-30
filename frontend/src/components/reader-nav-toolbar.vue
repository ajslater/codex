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
  </v-toolbar>
</template>

<script>
import { mapState } from "vuex";

import ReaderNavButton from "@/components/reader-nav-button";

export default {
  name: "ReaderNavToolbar",
  components: {
    ReaderNavButton,
  },
  computed: {
    ...mapState("reader", {
      maxPage: (state) => Number(state.maxPage),
    }),
  },
  methods: {
    routeToPage: function (page) {
      const params = { pk: Number(this.$route.params.pk), page };
      this.$store.dispatch("reader/routeTo", params);
    },
  },
};
</script>

<style scoped lang="scss">
.readerNavToolbar {
  position: fixed;
  bottom: 0px;
  width: 100%;
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

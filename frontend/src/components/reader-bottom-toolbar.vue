<template>
  <v-toolbar id="bottomToolbar" class="toolbar" dense transform="center bottom">
    <ReaderNavButton :value="0" />
    <v-slider
      id="slider"
      :value="pageNumber"
      min.number="+0"
      :max="maxPage"
      thumb-label
      hide-details="auto"
      dense
      @change="routeToPageNum($event)"
    />
    <ReaderNavButton :value="maxPage" />
  </v-toolbar>
</template>

<script>
import { mapGetters, mapState } from "vuex";

import ReaderNavButton from "@/components/reader-nav-button";

export default {
  name: "ReaderBottomToolbar",
  components: {
    ReaderNavButton,
  },
  computed: {
    ...mapState("reader", {
      maxPage: (state) => state.maxPage,
      pk: (state) => state.routes.current.pk,
      pageNumber: (state) => state.routes.current.pageNumber,
    }),
    ...mapGetters("reader", ["computedSettings"]),
    ...mapGetters("auth", ["isOpenToSee"]),
  },
  methods: {
    routeToPageNum: function (pageNumber) {
      const page = { pk: this.pk, pageNumber };
      this.$store.dispatch("reader/routeTo", page);
    },
  },
};
</script>

<style scoped lang="scss">
#bottomToolbar {
  position: fixed;
  bottom: 0px;
  width: 100%;
}
</style>

<!-- eslint-disable-next-line vue-scoped-css/require-scoped -->
<style lang="scss">
/* TOOLBARS */
.toolbar .v-toolbar__content {
  padding: 0px;
}
/* Custom slider with a large control. */
.v-input__slider .v-slider__thumb {
  height: 48px;
  width: 48px;
  left: -24px;
}
.v-input__slider .v-slider__thumb::before {
  left: -8px;
  top: -8px;
  height: 64px;
  width: 64px;
}
</style>
<!-- eslint-enable-next-line vue-scoped-css/require-scoped -->

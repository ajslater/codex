<template>
  <v-toolbar
    v-if="maxPage"
    class="readerNavToolbar codexToolbar"
    dense
    transform="center bottom"
  >
    <ReaderNavButton :value="0" />
    <PaginationSlider
      :key="comicLoaded"
      :value="+$route.params.page"
      :min="+0"
      :max="maxPage"
      :step="step"
      @change="routeToPage($event)"
    />
    <ReaderNavButton :value="maxPage" />
  </v-toolbar>
</template>

<script>
import { mapActions, mapState } from "pinia";

import PaginationSlider from "@/components/pagination-slider.vue";
import ReaderNavButton from "@/components/reader/reader-nav-button.vue";
import { useReaderStore } from "@/stores/reader";

export default {
  name: "ReaderNavToolbar",
  components: {
    PaginationSlider,
    ReaderNavButton,
  },
  computed: {
    ...mapState(useReaderStore, {
      maxPage: (state) => (state.comic ? state.comic.maxPage : 0),
      // without this the slider can fail to place right on book change
      comicLoaded: (state) => state.comicLoaded,
      step: (state) => {
        return state.computedSettings.twoPages ? 2 : 1;
      },
    }),
  },
  methods: {
    ...mapActions(useReaderStore, ["routeToPage"]),
  },
};
</script>

<style scoped lang="scss">
.readerNavToolbar {
  bottom: env(safe-area-inset-bottom);
  width: 100%;
  z-index: 10;
}
</style>

<!-- eslint-disable-next-line vue-scoped-css/enforce-style-type -->
<style lang="scss">
/* TOOLBARS */
#readerContainer .readerNavToolbar .v-toolbar__content {
  padding: 0px;
}
</style>

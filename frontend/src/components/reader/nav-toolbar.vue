<template>
  <v-toolbar
    v-if="maxPage"
    class="readerNavToolbar"
    dense
    transform="center bottom"
  >
    <ReaderNavButton :value="0" />
    <PaginationSlider
      :value="+$route.params.page"
      :min="+0"
      :max="maxPage"
      @change="routeToPage($event)"
    />
    <ReaderNavButton :value="maxPage" />
  </v-toolbar>
</template>

<script>
import { mapActions, mapState } from "pinia";

import PaginationSlider from "@/components/pagination-slider.vue";
import ReaderNavButton from "@/components/reader/nav-button.vue";
import { useReaderStore } from "@/stores/reader";

export default {
  name: "ReaderNavToolbar",
  components: {
    PaginationSlider,
    ReaderNavButton,
  },
  computed: {
    ...mapState(useReaderStore, {
      maxPage: (state) => state.comic.maxPage,
    }),
  },
  methods: {
    ...mapActions(useReaderStore, ["routeToPage"]),
  },
};
</script>

<style scoped lang="scss">
.readerNavToolbar {
  position: fixed;
  bottom: env(safe-area-inset-bottom);
  width: 100%;
}
</style>

<!-- eslint-disable-next-line vue-scoped-css/enforce-style-type -->
<style lang="scss">
/* TOOLBARS */
#readerContainer .readerNavToolbar .v-toolbar__content {
  padding: 0px;
}
</style>

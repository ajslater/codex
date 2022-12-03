<template>
  <v-toolbar
    v-if="maxPage"
    class="readerNavToolbar codexToolbar"
    density="compact"
    transform="center bottom"
  >
    <ReaderNavButton :value="0" />
    <PaginationSlider
      :key="$route.params.pk"
      :model-value="+$route.params.page"
      :min="+0"
      :max="maxPage"
      :step="step"
      :track-color="trackColor"
      @change="routeToPage($event)"
    />
    <ReaderNavButton :value="maxPage" :two-pages="twoPages" />
  </v-toolbar>
</template>

<script>
import { mapActions, mapGetters } from "pinia";

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
    ...mapGetters(useReaderStore, ["activeSettings", "activeBook"]),
    maxPage() {
      return this.activeBook ? this.activeBook.maxPage : 0;
    },
    twoPages() {
      return this.activeSettings.twoPages;
    },
    // without this the slider can fail to place right on book change
    step() {
      return this.activeSettings.twoPages ? 2 : 1;
    },
    trackColor() {
      return this.twoPages && +this.$route.params.page >= this.maxPage - 1
        ? this.$vuetify.theme.current.colors.primary
        : "";
    },
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

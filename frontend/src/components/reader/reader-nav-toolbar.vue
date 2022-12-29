<template>
  <PaginationToolbar v-if="maxPage">
    <ReaderNavButton :value="0" />
    <PaginationSlider
      :key="key"
      :model-value="+$route.params.page"
      :min="+0"
      :max="maxPage"
      :step="step"
      :track-color="trackColor"
      @update:model-value="routeToPage($event)"
    />
    <ReaderNavButton :value="maxPage" :two-pages="twoPages" />
  </PaginationToolbar>
</template>

<script>
import { mapActions, mapGetters } from "pinia";

import PaginationSlider from "@/components/pagination-slider.vue";
import PaginationToolbar from "@/components/pagination-toolbar.vue";
import ReaderNavButton from "@/components/reader/reader-nav-button.vue";
import { useReaderStore } from "@/stores/reader";

export default {
  name: "ReaderNavToolbar",
  components: {
    PaginationSlider,
    ReaderNavButton,
    PaginationToolbar,
  },
  computed: {
    ...mapGetters(useReaderStore, ["activeSettings", "activeBook"]),
    key() {
      return `${this.$route.params.pk} - ${this.twoPages}`;
    },
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

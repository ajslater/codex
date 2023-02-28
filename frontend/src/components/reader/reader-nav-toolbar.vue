<template>
  <PaginationToolbar v-if="maxPage">
    <ReaderBookChangeNavButton :direction="bookPrev" />
    <ReaderNavButton :value="min" :two-pages="twoPages" />
    <PaginationSlider
      :key="key"
      :model-value="+$route.params.page"
      :min="+0"
      :max="maxPage"
      :step="step"
      :track-color="trackColor"
      :reverse="readInReverse"
      @update:model-value="routeToPage($event)"
    />
    <ReaderNavButton :value="max" :two-pages="twoPages" />
    <ReaderBookChangeNavButton :direction="bookNext" />
  </PaginationToolbar>
</template>

<script>
import { mapActions, mapGetters } from "pinia";

import PaginationSlider from "@/components/pagination-slider.vue";
import PaginationToolbar from "@/components/pagination-toolbar.vue";
import ReaderBookChangeNavButton from "@/components/reader/reader-book-change-nav-button.vue";
import ReaderNavButton from "@/components/reader/reader-nav-button.vue";
import { useReaderStore } from "@/stores/reader";

export default {
  name: "ReaderNavToolbar",
  components: {
    PaginationSlider,
    ReaderNavButton,
    PaginationToolbar,
    ReaderBookChangeNavButton,
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
    readInReverse() {
      return this.activeSettings.readInReverse;
    },
    min() {
      return this.readInReverse ? this.maxPage : 0;
    },
    max() {
      return this.readInReverse ? 0 : this.maxPage;
    },
    bookPrev() {
      return this.readInReverse ? "next" : "prev";
    },
    bookNext() {
      return this.readInReverse ? "prev" : "next";
    },
  },
  methods: {
    ...mapActions(useReaderStore, ["routeToPage"]),
  },
};
</script>

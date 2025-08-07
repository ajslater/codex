<template>
  <PaginationToolbar v-if="numPages > 1">
    <BrowserNavButton :back="true" />
    <PaginationSlider
      :key="routeKey"
      :model-value="page"
      :min="+1"
      :max="numPages"
      :step="+1"
      @update:model-value="routeToPage($event)"
    />
    <BrowserNavButton :back="false" :more="true" />
  </PaginationToolbar>
</template>

<script>
import { mapActions, mapState } from "pinia";

import BrowserNavButton from "@/components/browser/toolbars/nav/browser-nav-button.vue";
import PaginationSlider from "@/components/pagination-slider.vue";
import PaginationToolbar from "@/components/pagination-toolbar.vue";
import { useBrowserStore } from "@/stores/browser";

export default {
  name: "BrowserNavToolbar",
  components: {
    BrowserNavButton,
    PaginationSlider,
    PaginationToolbar,
  },
  computed: {
    ...mapState(useBrowserStore, {
      numPages: (state) => state.page.numPages,
      routeKey: (state) => state.routeKey,
    }),
    page() {
      return +this.$route.params.page;
    },
  },
  methods: {
    ...mapActions(useBrowserStore, ["routeToPage"]),
    onUpdate($event) {
      this.routeToPage($event);
    },
  },
};
</script>

<template>
  <PaginationToolbar v-if="numPages > 1">
    <BrowserNavButton :back="true" />
    <PaginationSlider
      :model-value="+$route.params.page"
      :min="+1"
      :max="numPages"
      :step="1"
      @update:model-value="routeToPage($event)"
    />
    <BrowserNavButton :back="false" />
  </PaginationToolbar>
</template>

<script>
import { mapActions, mapState } from "pinia";

import BrowserNavButton from "@/components/browser/browser-nav-button.vue";
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
    }),
  },
  methods: {
    ...mapActions(useBrowserStore, ["routeToPage"]),
    onUpdate($event) {
      this.routeToPage($event);
    },
  },
};
</script>

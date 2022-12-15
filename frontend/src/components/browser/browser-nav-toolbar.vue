<template>
  <v-toolbar
    v-if="numPages > 1"
    class="paginationToolbar codexToolbar"
    density="compact"
  >
    <BrowserNavButton :back="true" />
    <PaginationSlider
      :model-value="+$route.params.page"
      :min="+1"
      :max="numPages"
      @update:modelValue="onUpdate"
    />
    <BrowserNavButton :back="false" />
  </v-toolbar>
</template>

<script>
import { mapActions, mapState } from "pinia";

import BrowserNavButton from "@/components/browser/browser-nav-button.vue";
import PaginationSlider from "@/components/pagination-slider.vue";
import { useBrowserStore } from "@/stores/browser";

export default {
  name: "BrowserNavToolbar",
  components: {
    BrowserNavButton,
    PaginationSlider,
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

<style scoped lang="scss">
.paginationToolbar {
  bottom: env(safe-area-inset-bottom);
  width: 100%;
  padding: 0px;
}
</style>

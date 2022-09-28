<template>
  <v-toolbar v-if="numPages > 1" class="paginationToolbar" dense>
    <BrowserNavButton :back="true" />
    <PaginationSlider
      :value="+$route.params.page"
      :min="+1"
      :max="numPages"
      @change="routeToPage($event)"
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
  },
};
</script>

<style scoped lang="scss">
.paginationToolbar {
  position: fixed;
  bottom: env(safe-area-inset-bottom);
  width: 100%;
  padding: 0px;
}
</style>

<!-- eslint-disable-next-line vue-scoped-css/enforce-style-type -->
<style lang="scss">
#browser .paginationToolbar > .v-toolbar__content {
  padding: 0px;
}
</style>

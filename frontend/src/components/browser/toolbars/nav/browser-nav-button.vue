<template>
  <PaginationNavButton
    :key="toRoute"
    :disabled="disabled"
    :title="title"
    :to="toRoute"
  >
    <v-icon v-if="showMore"> {{ mdiMagnify }}</v-icon>
    <v-icon :class="{ flipHoriz: !back }">
      {{ mdiChevronLeft }}
    </v-icon>
  </PaginationNavButton>
</template>

<script>
import { mdiChevronLeft, mdiMagnify } from "@mdi/js";
import { mapGetters, mapState } from "pinia";

import PaginationNavButton from "@/components/pagination-nav-button.vue";
import { useBrowserStore } from "@/stores/browser";
export default {
  name: "BrowserNavButton",
  components: {
    PaginationNavButton,
  },
  props: {
    back: {
      type: Boolean,
      required: true,
    },
    more: {
      type: Boolean,
      default: false,
    },
  },
  data() {
    return {
      mdiChevronLeft,
      mdiMagnify,
      routeParams: this.$route.params,
      page: +this.$route.params.page,
    };
  },
  computed: {
    ...mapGetters(useBrowserStore, ["isSearchMode"]),
    ...mapState(useBrowserStore, {
      numPages: (state) => state.page.numPages,
    }),
    increment() {
      return this.back ? -1 : 1;
    },
    toPage() {
      return this.page + this.increment;
    },
    title() {
      return this.showMore ? "Search for More" : "Page " + this.toPage;
    },
    toRoute() {
      const page = this.toPage;
      const params = { ...this.routeParams, page };
      return { params };
    },
    disabled() {
      return (
        (this.back && this.page <= 1) ||
        (!this.back && this.page >= this.numPages)
      );
    },
    showMore() {
      return this.more && this.toPage === this.numPages;
      // && this.isSearchLimitedMode
    },
  },
  watch: {
    $route(to) {
      this.params = to.params;
      this.page = +to.params.page;
    },
  },
};
</script>

<style scoped lang="scss">
.flipHoriz {
  transform: scaleX(-1);
}
</style>

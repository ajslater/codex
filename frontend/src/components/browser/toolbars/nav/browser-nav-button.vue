<template>
  <PaginationNavButton
    :key="routeKey"
    :class="classes"
    :disabled="disabled"
    :title="title"
    :to="toRoute"
  >
    <v-icon v-if="showMore">
      {{ mdiMagnify }}
    </v-icon>
    <v-icon :class="{ flipHoriz: !back }">
      {{ mdiChevronLeft }}
    </v-icon>
  </PaginationNavButton>
</template>

<script>
import { mdiChevronLeft, mdiMagnify } from "@mdi/js";
import { mapState } from "pinia";

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
    };
  },
  computed: {
    ...mapState(useBrowserStore, ["isSearchMode"]),
    ...mapState(useBrowserStore, {
      numPages: (state) => state.page.numPages,
      routeKey: (state) => state.routeKey,
    }),
    increment() {
      return this.back ? -1 : 1;
    },
    page() {
      return +this.$route.params.page;
    },
    routeParams() {
      return this.$route.params;
    },
    toPage() {
      return this.page + this.increment;
    },
    toRoute() {
      const params = { ...this.routeParams, page: this.toPage };
      return { params };
    },
    title() {
      return this.showMore ? "Search for More" : "Page " + this.toPage;
    },
    classes() {
      return {
        leftButton: this.back,
        rightButton: !this.back,
      };
    },
    disabled() {
      if (this.back) {
        return this.toPage < 1;
      } else {
        return this.toPage > this.numPages;
      }
    },
    showMore() {
      return this.more && this.isSearchMode && this.toPage === this.numPages;
    },
  },
};
</script>

<style scoped lang="scss">
.flipHoriz {
  transform: scaleX(-1);
}
.leftButton {
  padding-left: calc(10px + env(safe-area-inset-left));
}
.rightButton {
  padding-right: calc(10px + env(safe-area-inset-right));
}
</style>

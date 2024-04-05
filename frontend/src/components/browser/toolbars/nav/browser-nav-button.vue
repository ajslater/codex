<template>
  <PaginationNavButton
    :key="toRoute"
    :disabled="disabled"
    :title="title"
    :to="toRoute"
  >
    <v-icon :class="{ flipHoriz: !back }">
      {{ mdiChevronLeft }}
    </v-icon>
  </PaginationNavButton>
</template>

<script>
import { mdiChevronLeft } from "@mdi/js";
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
  },
  data() {
    return {
      mdiChevronLeft,
      routeParams: this.$route.params,
      page: +this.$route.params.page,
    };
  },
  computed: {
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
      return "Page " + this.toPage;
    },
    toRoute() {
      const page = this.toPage;
      const params = { ...this.routeParams, page };
      return { params };
    },
    disabled() {
      return (
        (this.back && +this.page <= 1) ||
        (!this.back && +this.page >= this.numPages)
      );
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

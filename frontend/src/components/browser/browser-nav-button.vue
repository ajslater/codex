<template>
  <PaginationNavButton :disabled="disabled" :title="title" :to="toRoute">
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
      return +this.$route.params.page + this.increment;
    },
    title() {
      return "to page" + this.toPage;
    },
    toRoute() {
      return { params: { ...this.$route.params, page: this.toPage } };
    },
    disabled() {
      return (
        (this.back && +this.$route.params.page <= 1) ||
        (!this.back && +this.$route.params.page >= this.numPages)
      );
    },
  },
};
</script>

<style scoped lang="scss">
.flipHoriz {
  transform: scaleX(-1);
}
</style>

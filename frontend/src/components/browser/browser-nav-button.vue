<template>
  <v-btn
    class="browserNavButton"
    :disabled="disabled"
    :title="toPage"
    height="100%"
    @click="routeToPage(toPage)"
  >
    <v-icon :class="{ flipHoriz: !back }">
      {{ mdiChevronLeft }}
    </v-icon>
  </v-btn>
</template>

<script>
import { mdiChevronLeft } from "@mdi/js";
import { mapActions, mapState } from "pinia";

import { useBrowserStore } from "@/stores/browser";
export default {
  name: "BrowserNavButton",
  props: {
    back: {
      type: Boolean,
      required: true,
    },
  },
  data() {
    return {
      mdiChevronLeft,
      page: 1,
      increment: this.back ? -1 : 1,
    };
  },
  computed: {
    ...mapState(useBrowserStore, {
      numPages: (state) => state.page.numPages,
    }),
    toPage: function () {
      return this.page + this.increment;
    },
    disabled: function () {
      return (
        (this.back && this.page <= 1) ||
        (!this.back && this.page >= this.numPages)
      );
    },
  },
  watch: {
    $route: function () {
      this.setPage();
    },
  },
  created: function () {
    this.setPage();
  },
  methods: {
    ...mapActions(useBrowserStore, ["routeToPage"]),
    setPage: function () {
      // This cannot be computed because router params are not reactive.
      this.page = Number(this.$route.params.page);
    },
  },
};
</script>

<style scoped lang="scss">
.browserNavButton {
  margin-inline-start: 0 !important;
  margin-inline-end: 0 !important;
}
.flipHoriz {
  transform: scaleX(-1);
}
</style>

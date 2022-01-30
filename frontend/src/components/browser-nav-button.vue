<template>
  <v-btn
    class="browserNavButton"
    :disabled="disabled"
    :title="toPage"
    large
    ripple
    @click="routeToPage"
  >
    <v-icon :class="{ flipHoriz: !back }">{{ mdiChevronLeft }}</v-icon>
  </v-btn>
</template>

<script>
import { mdiChevronLeft } from "@mdi/js";
import { mapState } from "vuex";

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
    ...mapState("browser", {
      numPages: (state) => Number(state.numPages),
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
    setPage: function () {
      // This cannot be computed because router params are not reactive.
      this.page = Number(this.$router.currentRoute.params.page);
    },
    routeToPage: function () {
      this.$store.dispatch("browser/routeToPage", this.toPage);
    },
  },
};
</script>

<style scoped lang="scss">
.browserNavButton {
  z-index: -1;
}
.flipHoriz {
  transform: scaleX(-1);
}
</style>

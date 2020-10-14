<template>
  <v-btn
    class="browserNavButton"
    :disabled="disabled"
    :to="toRoute"
    :title="nextPage"
    large
    ripple
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
    };
  },
  computed: {
    ...mapState("browser", {
      page: function (state) {
        if (!state.routes.current) {
          return null;
        }
        return state.routes.current.page;
      },
      numPages: (state) => state.numPages,
      toRoute: function (state) {
        if (!state.routes.current || !this.nextPage) {
          return "";
        }
        return {
          name: "browser",
          params: {
            pk: +state.routes.current.pk,
            group: state.routes.current.group,
            page: this.nextPage,
          },
        };
      },
    }),
    nextPage: function () {
      if (!this.page) {
        return null;
      }
      let increment;
      if (this.back) {
        increment = -1;
      } else {
        increment = 1;
      }
      return +this.page + increment;
    },
    disabled: function () {
      if (this.back) {
        return this.page <= 0;
      } else {
        return !this.numPages && this.page >= +this.numPages;
      }
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

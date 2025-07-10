<template>
  <v-slide-y-reverse-transition>
    <PaginationToolbar
      v-if="maxPage"
      v-show="showToolbars"
      id="readerToolbarNav"
    >
      <ReaderBookChangeNavButton :direction="bookPrev" :narrow="false" />
      <ReaderNavButton :value="min" :two-pages="twoPages" />
      <PaginationSlider
        :key="key"
        :model-value="storePage"
        :min="+0"
        :max="maxPage"
        :step="step"
        :track-color="trackColor"
        :reverse="isReadInReverse"
        @update:model-value="onSliderUpdate($event)"
      />
      <ReaderNavButton :value="max" :two-pages="twoPages" />
      <ReaderBookChangeNavButton :direction="bookNext" :narrow="false" />
    </PaginationToolbar>
  </v-slide-y-reverse-transition>
</template>

<script>
import { mapActions, mapState } from "pinia";

import PaginationSlider from "@/components/pagination-slider.vue";
import PaginationToolbar from "@/components/pagination-toolbar.vue";
import ReaderBookChangeNavButton from "@/components/reader/toolbars/nav/reader-book-change-nav-button.vue";
import ReaderNavButton from "@/components/reader/toolbars/nav/reader-nav-button.vue";
import { useAuthStore } from "@/stores/auth";
import { useReaderStore } from "@/stores/reader";

const PREV = "prev";
const NEXT = "next";

export default {
  name: "ReaderNavToolbar",
  components: {
    PaginationSlider,
    ReaderNavButton,
    PaginationToolbar,
    ReaderBookChangeNavButton,
  },
  computed: {
    ...mapState(useAuthStore, ["isAuthDialogOpen"]),
    ...mapState(useReaderStore, [
      "activeSettings",
      "isReadInReverse",
      "isVertical",
    ]),
    ...mapState(useReaderStore, {
      showToolbars: (state) => state.showToolbars,
      storePage: (state) => state.page,
      key(state) {
        const pk = state.books?.current?.pk;
        return `${pk}:${this.step}:${this.isReadInReverse}`;
      },
      maxPage: (state) => state.books?.current?.maxPage || 0,
    }),
    twoPages() {
      return this.activeSettings.twoPages;
    },
    // without this the slider can fail to place right on book change
    step() {
      return this.activeSettings.twoPages ? 2 : 1;
    },
    trackColor() {
      return this.twoPages && +this.storePage >= this.maxPage - 1
        ? this.$vuetify.theme.current.colors.primary
        : "";
    },
    min() {
      return this.isReadInReverse ? this.maxPage : 0;
    },
    max() {
      return this.isReadInReverse ? 0 : this.maxPage;
    },
    bookPrev() {
      return this.isReadInReverse ? "next" : "prev";
    },
    bookNext() {
      return this.isReadInReverse ? "prev" : "next";
    },
  },
  mounted() {
    document.addEventListener("keyup", this._keyUpListener);
  },
  beforeUnmount() {
    document.removeEventListener("keyup", this._keyUpListener);
  },
  methods: {
    ...mapActions(useReaderStore, [
      "routeToBook",
      "routeToDirection",
      "routeToDirectionOne",
      "routeToPage",
      "setActivePage",
    ]),
    onSliderUpdate(page) {
      if (this.isVertical) {
        this.setActivePage(page, true);
      } else {
        this.routeToPage(page);
      }
    },
    _keyUpListener(event) {
      event.stopPropagation();
      if (this.isAuthDialogOpen) {
        return;
      }
      switch (event.key) {
        case " ":
          if (
            !event.shiftKey &&
            window.innerHeight + window.scrollY + 1 >=
              document.body.scrollHeight
          ) {
            // Spacebar goes next only at the bottom of page
            this.routeToDirection(NEXT);
          } else if (
            // Shift + Spacebar goes back only at the top of page
            !!event.shiftKey &&
            window.scrollY === 0
          ) {
            this.routeToDirection(PREV);
          }
          break;
        case "j":
        case "ArrowRight":
          this.routeToDirection(NEXT);
          break;
        case "k":
        case "ArrowLeft":
          this.routeToDirection(PREV);
          break;
        case ",":
          this.routeToDirectionOne(PREV);
          break;
        case ".":
          this.routeToDirectionOne(NEXT);
          break;
        case "n":
          this.routeToBook(NEXT);
          break;
        case "p":
          this.routeToBook(PREV);
          break;
        // No default
      }
    },
  },
};
</script>
<style scoped lang="scss">
#readerToolbarNav {
  padding-left: 0px; // given to button;
  padding-right: 0px; // given to button.
  padding-bottom: env(safe-area-inset-top);
}
</style>

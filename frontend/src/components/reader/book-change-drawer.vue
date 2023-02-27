<template>
  <v-navigation-drawer
    v-if="show"
    :class="{ bookChangeDrawer: true, [direction]: true }"
    disable-resize-watcher
    disable-route-watcher
    :location="computedDirection === 'prev' ? 'left' : 'right'"
    :model-value="isDrawerOpen"
    :scrim="false"
    temporary
    touchless
  >
    <router-link
      class="navLink"
      :to="route"
      :aria-label="label"
      :title="label"
      @click="$event.stopImmediatePropagation()"
    >
      <v-icon class="bookChangeIcon"> {{ icon }} </v-icon>
    </router-link>
  </v-navigation-drawer>
</template>
<script>
import { mdiBookArrowDown, mdiBookArrowUp } from "@mdi/js";
import { mapActions, mapGetters, mapState } from "pinia";

import { getComicPageSource } from "@/api/v3/reader";
import { linksInfo } from "@/components/reader/prefetch-links";
import { useReaderStore } from "@/stores/reader";

export default {
  name: "BookChangeDrawer",
  props: {
    direction: {
      type: String,
      required: true,
    },
  },
  head() {
    return linksInfo([this.prefetchSrc1, this.prefetchSrc2]);
  },
  computed: {
    ...mapGetters(useReaderStore, ["prevBookChangeShow", "nextBookChangeShow"]),
    ...mapState(useReaderStore, {
      prefetchSrc2(state) {
        if (!this.params) {
          return false;
        }
        const book = state.books.get(this.params.pk);
        const otherBookSettings = this.getSettings(state.readerSettings, book);
        if (!this.isDrawerOpen || !this.params || !otherBookSettings.twoPages) {
          return false;
        }
        const params = { pk: this.params.pk, page: this.params.page + 1 };
        return getComicPageSource(params);
      },
      isDrawerOpen(state) {
        return state.bookChange === this.computedDirection;
      },
      params(state) {
        return state.routes.books[this.computedDirection];
      },
      icon() {
        return this.computedDirection === "next"
          ? mdiBookArrowDown
          : mdiBookArrowUp;
      },
    }),
    show() {
      return this[this.computedDirection + "BookChangeShow"];
    },
    prefetchSrc1() {
      if (!this.isDrawerOpen || !this.params) {
        return false;
      }
      return getComicPageSource(this.params);
    },
    route() {
      return this.params ? { params: this.params } : {};
    },
    label() {
      const prefix = this.computedDirection === "prev" ? "Previous" : "Next";
      return `${prefix} Book`;
    },
    computedDirection() {
      return this.normalizeDirection(this.direction);
    },
  },
  methods: {
    ...mapActions(useReaderStore, ["getSettings", "normalizeDirection"]),
  },
};
</script>
<style scoped lang="scss">
.prev {
  cursor: n-resize;
  left: 0px;
}
.next {
  cursor: s-resize;
  right: 0px;
}
.navLink {
  display: block;
  height: 100%;
}
$iconSize: 25%;
.bookChangeIcon {
  top: 50%;
  left: 50%;
  transform: translateX(-50%) translateY(-50%);
  height: $iconSize;
  width: $iconSize;
  color: white;
}
</style>
<!-- eslint-disable-next-line vue-scoped-css/enforce-style-type -->
<style lang="scss">
.bookChangeDrawer {
  width: 33vw !important;
  opacity: 0.75 !important;
  z-index: 15 !important;
}
</style>

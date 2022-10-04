<template>
  <v-navigation-drawer
    class="changeBookDrawer"
    :class="classes"
    absolute
    :left="direction === 'prev'"
    :right="direction === 'next'"
    temporarary
    :value="isDrawerOpen"
    width="33%"
  >
    <router-link
      class="navLink"
      :to="route"
      :aria-label="label"
      :title="label"
      @click.native="$event.stopImmediatePropagation()"
    >
      <v-icon class="bookChangeIcon"> {{ icon }} </v-icon>
    </router-link>
  </v-navigation-drawer>
</template>
<script>
import { mdiBookArrowDown, mdiBookArrowUp } from "@mdi/js";
import { mapState } from "pinia";

import { getComicPageSource } from "@/api/v3/reader";
import { useReaderStore } from "@/stores/reader";

export default {
  name: "ChangeBookDrawer",
  props: {
    direction: {
      type: String,
      required: true,
    },
  },
  data() {
    return {
      icon: this.direction === "next" ? mdiBookArrowDown : mdiBookArrowUp,
      classes: { [this.direction]: true },
    };
  },
  head() {
    if (this.prefetchSrc) {
      return { link: { rel: "prefetch", as: "image", href: this.prefetchSrc } };
    }
  },
  computed: {
    ...mapState(useReaderStore, {
      isDrawerOpen(state) {
        return state.bookChange === this.direction;
      },
      series: (state) => state.comic.series,
      prefetchSrc(state) {
        if (this.isDrawerOpen && this.params) {
          return getComicPageSource(this.params, state.timestamp);
        }
      },
    }),
    params() {
      return this.series[this.direction];
    },
    route() {
      return this.series && this.series[this.direction]
        ? { params: this.params }
        : {};
    },
    label() {
      const prefix = this.direction === "prev" ? "Previous" : "Next";
      return `${prefix} Book`;
    },
  },
};
</script>
<style scoped lang="scss">
.changeBookDrawer {
  position: fixed;
  height: 100vh;
  opacity: 0.75;
  z-index: 15;
}
.prev {
  cursor: n-resize;
}
.next {
  cursor: s-resize;
}
.navLink {
  display: block;
  height: 100%;
}
.bookChangeIcon {
  top: 50%;
  left: 50%;
  transform: translateX(-50%) translateY(-50%);
}
</style>
<!-- eslint-disable-next-line vue-scoped-css/enforce-style-type -->
<style lang="scss">
$iconSize: 96px;
.bookChangeIcon svg {
  height: $iconSize !important;
  width: $iconSize !important;
  font-size: $iconSize !important;
}
</style>

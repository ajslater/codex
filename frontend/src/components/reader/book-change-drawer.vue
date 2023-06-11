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
    if (this.isDrawerOpen) {
      return this.prefetchLinks(this.params, this.computedDirection, true);
    }
  },
  computed: {
    ...mapGetters(useReaderStore, ["prevBookChangeShow", "nextBookChangeShow"]),
    ...mapState(useReaderStore, {
      computedDirection() {
        return this.normalizeDirection(this.direction);
      },
      params(state) {
        return state.routes.books[this.computedDirection];
      },
      isDrawerOpen(state) {
        return state.bookChange === this.computedDirection;
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
    route() {
      return this.toRoute(this.params);
    },
    label() {
      return this.linkLabel(this.computedDirection, "Book");
    },
  },
  methods: {
    ...mapActions(useReaderStore, [
      "getSettings",
      "linkLabel",
      "normalizeDirection",
      "prefetchLinks",
      "toRoute",
    ]),
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

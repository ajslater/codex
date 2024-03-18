<template>
  <v-navigation-drawer
    v-if="show"
    class="bookChangeDrawer"
    disable-resize-watcher
    disable-route-watcher
    :location="drawerLocation"
    :model-value="isDrawerOpen"
    :scrim="false"
    temporary
    touchless
  >
    <router-link
      :class="{ navLink: true, [cursorClass]: true }"
      :to="route"
      :aria-label="label"
      :title="label"
      @click="$event.stopImmediatePropagation()"
    >
      <v-icon class="bookChangeIcon">
        {{ icon }}
      </v-icon>
    </router-link>
  </v-navigation-drawer>
</template>
<script>
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
    ...mapGetters(useReaderStore, ["isBTT"]),
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
        return this.bookChangeIcon(this.computedDirection);
      },
    }),
    drawerLocation() {
      return this.bookChangeLocation(this.direction);
    },
    cursorClass() {
      return this.bookChangeCursorClass(this.computedDirection);
    },
    show() {
      return this.bookChangeShow(this.computedDirection);
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
      "bookChangeLocation",
      "bookChangeCursorClass",
      "bookChangeShow",
      "bookChangeIcon",
    ]),
  },
};
</script>
<style scoped lang="scss">
.prevCursor {
  cursor: n-resize;
  /*
  left: 0px;
  */
}
.nextCursor {
  cursor: s-resize;
  /*
  right: 0px;
  */
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

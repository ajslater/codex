<template>
  <v-navigation-drawer
    v-if="show"
    class="bookChangeDrawer"
    disable-resize-watcher
    disable-route-watcher
    :location="drawerLocation"
    :model-value="isDrawerOpen"
    :scrim="false"
    :class="{ drawerActivated: isDrawerOpen }"
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
import { mapActions, mapState } from "pinia";

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
    ...mapState(useReaderStore, ["isBTT"]),
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
.bookChangeDrawer {
  opacity: 0.75 !important;
  z-index: 15 !important;
}
.drawerActivated {
  // Deactivated drawers with custom width don't move off the screen enough
  width: 33vw !important;
}

.prevCursor {
  cursor: n-resize;
}
.nextCursor {
  cursor: s-resize;
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

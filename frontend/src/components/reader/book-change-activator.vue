<template>
  <div
    v-if="show"
    class="bookChangeColumn"
    :class="{ [positionClass]: true, [cursorClass]: true }"
    @click.stop="setBookChangeFlag(direction)"
  />
  <BookChangeDrawer :direction="direction" />
</template>
<script>
import { mapActions } from "pinia";

import BookChangeDrawer from "@/components/reader/book-change-drawer.vue";
import { useReaderStore } from "@/stores/reader";

export default {
  name: "BookChangeActivator",
  components: {
    BookChangeDrawer,
  },
  props: {
    direction: {
      type: String,
      required: true,
    },
  },
  computed: {
    computedDirection() {
      return this.normalizeDirection(this.direction);
    },
    positionClass() {
      const pos = this.bookChangeLocation(this.direction);
      return pos + "Pos";
    },
    cursorClass() {
      return this.bookChangeCursorClass(this.direction);
    },
    show() {
      return this.bookChangeShow(this.computedDirection);
    },
  },
  methods: {
    ...mapActions(useReaderStore, [
      "setBookChangeFlag",
      "normalizeDirection",
      "bookChangeLocation",
      "bookChangeCursorClass",
      "bookChangeShow",
    ]),
  },
};
</script>
<style scoped lang="scss">
.bookChangeColumn {
  position: fixed;
  top: 48px;
  height: calc(100vh - 96px);
  width: 33vw;
}
.leftPos {
  left: 0px;
}
.rightPos {
  right: 0px;
}
.upCursor {
  cursor: n-resize;
}
.downCursor {
  cursor: s-resize;
}
</style>

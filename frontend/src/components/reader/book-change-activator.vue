<template>
  <div
    v-if="show"
    class="changeColumn"
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
    show() {
      return this.bookChangeShow(this.computedDirection);
    },
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
  },
  methods: {
    ...mapActions(useReaderStore, [
      "bookChangeCursorClass",
      "bookChangeLocation",
      "bookChangeShow",
      "normalizeDirection",
      "setBookChangeFlag",
    ]),
  },
};
</script>
<style scoped lang="scss">
@forward "./change-column";

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

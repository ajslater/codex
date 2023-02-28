<template>
  <div
    v-if="show"
    class="bookChangeColumn"
    :class="{ [direction]: true }"
    @click.stop="setBookChangeFlag(direction)"
  />
</template>
<script>
import { mapActions, mapGetters } from "pinia";

import { useReaderStore } from "@/stores/reader";

export default {
  name: "BookChangeActivator",
  props: {
    direction: {
      type: String,
      required: true,
    },
  },
  computed: {
    ...mapGetters(useReaderStore, ["prevBookChangeShow", "nextBookChangeShow"]),
    show() {
      return this[this.computedDirection + "BookChangeShow"];
    },
    computedDirection() {
      return this.normalizeDirection(this.direction);
    },
  },
  methods: {
    ...mapActions(useReaderStore, ["setBookChangeFlag", "normalizeDirection"]),
  },
};
</script>
<style scoped lang="scss">
.bookChangeColumn {
  position: fixed;
  height: 100%;
  width: 33vw;
}
.prev {
  cursor: n-resize;
  left: 0px;
}
.next {
  cursor: s-resize;
  right: 0px;
}
</style>

<template>
  <router-link
    v-if="show"
    :to="route"
    :aria-label="label"
    :class="{
      [pageChangeClass]: true,
      [directionClass]: true,
    }"
    @click="$event.stopImmediatePropagation()"
  />
</template>
<script>
import { mapActions, mapGetters, mapState } from "pinia";

import { useReaderStore } from "@/stores/reader";

export default {
  name: "PageChangeLink",
  props: {
    direction: { type: String, required: true },
  },
  head() {
    return this.prefetchLinks(this.params, this.computedDirection);
  },
  computed: {
    ...mapGetters(useReaderStore, ["isVertical", "isFirstPage", "isLastPage"]),
    ...mapState(useReaderStore, {
      params(state) {
        return state.routes[this.computedDirection];
      },
    }),
    computedDirection() {
      return this.normalizeDirection(this.direction);
    },
    show() {
      return this.computedDirection === "prev"
        ? !this.isFirstPage
        : !this.isLastPage;
    },
    pageChangeClass() {
      let pcc = "pageChange";
      pcc += this.isVertical ? "Row" : "Column";
      return pcc;
    },
    directionClass() {
      let dc = this.direction;
      if (this.isVertical) {
        dc += "Vertical";
      }
      return dc;
    },
    route() {
      return this.toRoute(this.params);
    },
    label() {
      return this.linkLabel(this.computedDirection, "Page");
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
.pageChangeColumn {
  position: fixed;
  top: 48px;
  height: calc(100vh - 96px);
  width: 33vw;
}
.pageChangeRow {
  position: fixed;
  height: 33vh;
  width: 100%;
}
.prev {
  left: 0px;
  cursor: w-resize;
}
.prevVertical {
  top: 0px;
  cursor: n-resize;
}
.next {
  right: 0px;
  cursor: e-resize;
}
.nextVertical {
  bottom: 0px;
  cursor: s-resize;
}
</style>

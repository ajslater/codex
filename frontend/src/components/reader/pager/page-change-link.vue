<template>
  <router-link
    v-if="show"
    :to="route"
    :aria-label="label"
    class="changeColumn"
    :class="{
      [directionClass]: true,
    }"
    @click="$event.stopImmediatePropagation()"
  />
</template>
<script>
import { mapActions, mapState } from "pinia";

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
    ...mapState(useReaderStore, ["isFirstPage", "isLastPage"]),
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
      return "pageChangeColumn";
    },
    directionClass() {
      return this.direction;
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
      "linkLabel",
      "normalizeDirection",
      "prefetchLinks",
      "toRoute",
    ]),
  },
};
</script>
<style scoped lang="scss">
@forward "../change-column";

.prev {
  left: 0px;
  cursor: w-resize;
}

.next {
  right: 0px;
  cursor: e-resize;
}
</style>

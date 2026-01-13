<template>
  <div
    v-drag-scroller.onlyX
    class="scaleForScroll"
    :style="style"
    @dblclick="onDoubleClick"
  >
    <slot />
    <v-icon v-if="showReset" class="resetIcon" @click.stop="scaleReset">
      {{ mdiMagnifyMinusOutline }}
    </v-icon>
  </div>
</template>

<script>
import { mdiMagnifyMinusOutline } from "@mdi/js";
import { mapActions, mapState } from "pinia";

import { SCALE_DEFAULT, useReaderStore } from "@/stores/reader";

const SCALE_INCREMENT = 0.5;

export default {
  name: "ScaleForScroll",
  emits: ["click"],
  data() {
    return {
      mdiMagnifyMinusOutline,
    };
  },
  computed: {
    ...mapState(useReaderStore, {
      scale: (state) => state.clientSettings.scale,
    }),
    showReset() {
      return this.scale != SCALE_DEFAULT;
    },
    style() {
      const cursor = this.scale == SCALE_DEFAULT ? "zoom-in" : "all-scroll";
      return {
        cursor,
      };
    },
  },
  methods: {
    ...mapActions(useReaderStore, ["setSettingsClient"]),
    clearSelection() {
      // Desktop safari often selects text on double-click.
      if (globalThis.getSelection) {
        globalThis.getSelection().removeAllRanges();
      }
    },
    onDoubleClick() {
      this.clearSelection();
      const scale = this.scale + SCALE_INCREMENT;
      this.setSettingsClient({ scale });
    },
    scaleReset() {
      this.setSettingsClient({ scale: SCALE_DEFAULT });
    },
  },
};
</script>

<style scoped lang="scss">
.scaleForScroll {
  overflow: scroll;
  // one finger horizontal scrolling for mobile safari
  -webkit-overflow-scrolling: touch;
}

.resetIcon {
  position: fixed;
  bottom: calc(env(safe-area-inset-bottom) + 45px);
  right: 50%;
  transform: translate(50%, 0);
  z-index: 200;
  font-size: 50px;
  color: white;
  filter: drop-shadow(1px 1px 1px black);
  opacity: 0.666;
}

.resetIcon:hover {
  opacity: 1;
}
</style>

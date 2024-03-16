<template>
  <img
    :class="fitToClass"
    class="img"
    :src="src"
    :style="style"
    v-bind="$attrs"
    @error="$emit('error', $event)"
    @load="$emit('load', $event)"
  />
</template>
<script>
import { mapState } from "pinia";

import { useReaderStore } from "@/stores/reader";
export default {
  name: "ImgPage",
  props: {
    src: { type: String, required: true },
    fitToClass: { type: Object, required: true },
  },
  emits: ["load", "error"],
  computed: {
    ...mapState(useReaderStore, {
      scale: (state) => state.clientSettings.scale,
    }),
    style() {
      // Magic for transform: scale() not positioning elements right.
      const s = {};
      if (this.scale == 1) {
        return s;
      }
      const img = this.$el;
      if (!img?.naturalWidth) {
        return s;
      }
      const left = img.naturalWidth / 2;
      s.transformOrigin = `${left}px top`;
      // Scale the image.
      s.transform = `scale(${this.scale})`;
      return s;
    },
  },
};
</script>

<style scoped lang="scss">
.img {
  transition: transform 0.5s ease-in-out;
}

.fitToScreen,
.fitToScreenTwo {
  height: 100vh;
  object-fit: contain;
}

.fitToScreen {
  width: 100vw;
}

.fitToScreenTwo {
  max-width: 50vw;
}

.fitToScreenVertical {
  height: 50vh;
  object-fit: contain;
}

.fitToHeight,
.fitToHeightTwo,
.fitToHeightVertical {
  height: 100vh;
}

.fitToWidth,
.fitToWidthVertical {
  width: 100vw;
}

.fitToWidthTwo {
  width: 50vw;
}

.fitToOrig,
.fitToOrigTwo,
.fitToOrigVertical {
  object-fit: none;
}
</style>

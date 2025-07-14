<template>
  <img
    :class="classes"
    class="img"
    draggable="false"
    :src="src"
    :style="style"
    v-bind="$attrs"
    @error="$emit('error', $event)"
    @load="$emit('load', $event)"
  />
</template>
<script>
import { mapActions, mapState } from "pinia";

import { useReaderStore } from "@/stores/reader";
export default {
  name: "ImgPage",
  props: {
    book: { type: Object, required: true },
    src: { type: String, required: true },
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
    bookSettings() {
      return this.getBookSettings(this.book);
    },
    classes() {
      return this.bookSettings.fitToClass;
    },
  },
  methods: {
    ...mapActions(useReaderStore, ["getBookSettings"]),
  },
};
</script>

<style scoped lang="scss">
/*
.img {
  transition: transform 0.5s ease-in-out;
}
*/

.fitToScreen,
.fitToScreenTwo,
.fitToScreenVertical {
  object-fit: contain;
}

.fitToScreen,
.fitToScreenTwo,
.fitToScreenVertical,
.fitToHeight,
.fitToHeightTwo,
.fitToHeightVertical {
  height: 100vh;
}

.fitToScreenTwo {
  max-width: 50vw;
}

.fitToWidth,
.fitToWidthVertical,
.fitToScreen,
.fitToScreenVertical {
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

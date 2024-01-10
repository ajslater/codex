<template>
  <img
    :class="fitToClass"
    :src="src"
    v-bind="$attrs"
    @error="$emit('error')"
    @load="$emit('load')"
  />
</template>
<script>
export default {
  name: "ImgPage",
  props: {
    src: { type: String, required: true },
    fitToClass: { type: Object, required: true },
  },
  emits: ["load", "error"],
};
</script>

<style scoped lang="scss">
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

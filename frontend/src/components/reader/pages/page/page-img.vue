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
.fitToScreenTwoVertical {
  height: 50vh;
  object-fit: contain;
}
.fitToScreen {
  width: 100vw;
}
.fitToHeight,
.fitToHeightTwo {
  height: 100vh;
}
.fitToHeightTwoVertical {
  height: 50vh;
}
.fitToWidth {
  width: 100vw;
}
.fitToWidthTwo {
  width: 50vw;
}
.fitToWidthTwoVertical {
  width: 100vw;
}

.fitToScreenTwo {
  max-width: 50vw;
}
.fitToOrig,
.fitToOrigTwo,
.fitToOrigTwoVertical {
  object-fit: none;
}
</style>

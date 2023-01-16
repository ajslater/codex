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
    pk: { type: Number, required: true },
    src: { type: String, required: true },
    settings: { type: Object, required: true },
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
.fitToHeight,
.fitToHeightTwo {
  height: 100vh;
}
.fitToWidth {
  width: 100vw;
}
.fitToWidthTwo {
  width: 50vw;
}
.fitToScreenTwo {
  max-width: 50vw;
}
.fitToOrig,
.fitToOrigTwo {
  object-fit: none;
}
</style>

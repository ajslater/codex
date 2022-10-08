<template>
  <img :class="fitToClass" :src="src" v-on="$listeners" />
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
  max-height: 100vh;
}
.fitToScreen {
  max-width: 100vw;
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

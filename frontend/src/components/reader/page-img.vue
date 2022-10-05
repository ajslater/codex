<template>
  <img :class="fitToClass" :src="src" v-on="$listeners" />
</template>
<script>
import { mapGetters } from "pinia";

import { useReaderStore } from "@/stores/reader";
export default {
  name: "ImgPage",
  props: {
    src: { type: String, required: true },
  },
  emits: ["load", "error"],
  computed: {
    ...mapGetters(useReaderStore, ["fitToClass"]),
  },
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

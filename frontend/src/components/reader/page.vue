<template>
  <img
    :class="fitToClass"
    :src="src"
    :alt="`Page ${page}`"
    @error="changeSrcToError"
  />
</template>
<script>
import { mapGetters, mapState } from "pinia";

import { getComicPageSource } from "@/api/v3/reader";
import { useReaderStore } from "@/stores/reader";
export default {
  name: "ComicPage",
  props: {
    pk: { type: Number, required: true },
    page: { type: Number, required: true },
  },
  computed: {
    ...mapGetters(useReaderStore, ["fitToClass"]),
    ...mapState(useReaderStore, {
      src(state) {
        const params = { pk: this.pk, page: this.page };
        return getComicPageSource(params, state.timestamp);
      },
    }),
  },
  methods: {
    changeSrcToError(event) {
      event.target.src = window.CODEX.MISSING_PAGE;
    },
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

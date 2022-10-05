<template>
  <div class="pageLoading" :class="{ twoPages }">
    <Placeholder class="pagePlaceholder" />
  </div>
</template>
<script>
import { mapGetters } from "pinia";

import Placeholder from "@/components/placeholder-loading.vue";
import { useReaderStore } from "@/stores/reader";

export default {
  name: "LoadingPage",
  components: { Placeholder },
  computed: {
    ...mapGetters(useReaderStore, ["computedSettings"]),
    twoPages() {
      return this.computedSettings.twoPages;
    },
  },
};
</script>

<style scoped lang="scss">
.pageLoading {
  display: inline-flex;
  height: 100vh;
  width: 100vw;
  justify-content: center;
  align-items: center;
}
.twoPages {
  max-width: 50vw;
}
.pagePlaceholder {
  height: 50% !important;
  width: 50% !important;
}
</style>

<template>
  <v-toolbar
    v-if="isBanner"
    id="banner"
    height="36"
    density="compact"
    flat
    :title="banner"
  />
</template>
<script>
import { mapGetters, mapState } from "pinia";

import { useAuthStore } from "@/stores/auth";
export default {
  name: "AppBanner",
  computed: {
    ...mapGetters(useAuthStore, ["isBanner"]),
    ...mapState(useAuthStore, {
      banner: (state) => state.adminFlags.bannerText,
    }),
  },
};
</script>
<style scoped lang="scss">
#banner {
  padding-left: env(safe-area-inset-left);
  padding-right: env(safe-area-inset-right);
  width: 100%;
  text-align: center;
}
#banner :deep(.v-toolbar-title) {
  margin: 0px;
}
</style>

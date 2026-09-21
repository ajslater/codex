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
import { mapState } from "pinia";

import { useAuthStore } from "@/stores/auth";
export default {
  name: "AppBanner",
  computed: {
    ...mapState(useAuthStore, ["isBanner"]),
    ...mapState(useAuthStore, {
      banner: (state) => state.adminFlags.bannerText,
    }),
  },
};
</script>
<style scoped lang="scss">
/* Layered: these rules beat Vuetify's component CSS by position,
 * and lose to a `color`/utility prop, which is the intended order. */
@layer codex-components {
  #banner {
    padding-top: max(env(safe-area-inset-top), 5px);
    padding-left: env(safe-area-inset-left);
    padding-right: env(safe-area-inset-right);
    width: 100%;
    text-align: center;
  }
  #banner :deep(.v-toolbar-title) {
    margin: 0px;
  }
}
</style>

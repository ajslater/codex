<template>
  <v-btn class="closeButton" :icon="mdiClose" v-bind="$attrs" />
</template>
<script>
import { mdiClose } from "@mdi/js";
export default {
  name: "CloseButton",
  data() {
    return {
      mdiClose,
    };
  },
};
</script>

<style scoped lang="scss">
/* Layered: these rules beat Vuetify's component CSS by position,
 * and lose to a `color`/utility prop, which is the intended order. */
@layer codex-components {
  .closeButton :deep(.v-icon) {
    margin-right: 0 !important;
  }
}
</style>

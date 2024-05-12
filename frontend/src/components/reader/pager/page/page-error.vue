<template>
  <v-empty-state
    class="pageError"
    :class="{ twoPages }"
    :headline="text"
    :icon="icon"
  />
</template>
<script>
import { mdiAlertCircleOutline, mdiLockOutline } from "@mdi/js";
const UNAUTHORIZED_TYPE = "unauthorized";

export default {
  name: "ErrorPage",
  props: {
    twoPages: { type: Boolean, required: true },
    type: { type: String, required: true },
  },
  computed: {
    text() {
      return this.type === UNAUTHORIZED_TYPE
        ? "Protected page"
        : "Failed to load page";
    },
    icon() {
      return this.type === UNAUTHORIZED_TYPE
        ? mdiLockOutline
        : mdiAlertCircleOutline;
    },
  },
};
</script>
<style scoped lang="scss">
.pageError {
  height: 100vh;
}
.pageError :deep(.v-icon),
.pageError :deep(.v-empty-state__headline) {
  color: rgb(var(--v-theme-error)) !important;
}
.twoPages {
  max-width: 50vw;
}
</style>

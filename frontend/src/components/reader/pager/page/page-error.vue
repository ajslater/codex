<template>
  <EmptyState
    class="pageError"
    :class="{ twoPages }"
    :headline="text"
    :icon="icon"
    action-text="Retry"
    @click:action="onAction"
  />
</template>
<script>
import { mdiAlertCircleOutline, mdiLockOutline } from "@mdi/js";

import EmptyState from "@/components/empty.vue";

const UNAUTHORIZED_TYPE = "unauthorized";

export default {
  name: "ErrorPage",
  components: { EmptyState },
  props: {
    twoPages: { type: Boolean, required: true },
    type: { type: String, required: true },
  },
  emits: ["retry"],
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
  methods: {
    onAction(event) {
      this.$emit("retry", event);
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

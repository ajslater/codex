<template>
  <v-btn
    v-if="isUserAdmin && pendingPrompts.length > 0"
    variant="flat"
    color="warning"
    size="small"
    class="promptButton"
    @click="promptDialogOpen = true"
  >
    <v-icon start>{{ mdiTagMultiple }}</v-icon>
    {{ pendingPrompts.length }} Prompt{{
      pendingPrompts.length === 1 ? "" : "s"
    }}
  </v-btn>
</template>

<script>
import { mdiTagMultiple } from "@mdi/js";
import { mapState, mapWritableState } from "pinia";

import { useAuthStore } from "@/stores/auth";
import { useOnlineTagStore } from "@/stores/online-tag";

export default {
  name: "OnlineTagPromptButton",
  data() {
    return { mdiTagMultiple };
  },
  computed: {
    ...mapState(useAuthStore, ["isUserAdmin"]),
    ...mapState(useOnlineTagStore, ["pendingPrompts"]),
    ...mapWritableState(useOnlineTagStore, ["promptDialogOpen"]),
  },
};
</script>

<style scoped lang="scss">
.promptButton {
  animation: pulse 2s ease-in-out infinite;
}

@keyframes pulse {
  0%,
  100% {
    opacity: 1;
  }
  50% {
    opacity: 0.6;
  }
}
</style>

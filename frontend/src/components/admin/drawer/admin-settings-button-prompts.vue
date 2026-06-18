<!--
  An amber dot overlaid on the settings (hamburger) button when online-tagging
  matches are waiting for an admin to review. Mirrors
  admin-settings-button-errors.vue but uses the notification (warning) color and
  the opposite corner so the two dots never overlap. Pending prompts are synced
  app-wide on socket (re)connect, so no load is needed here.
-->
<template>
  <span
    v-if="hasPrompts"
    class="promptDot"
    title="Online tagging matches to review"
  />
</template>

<script>
import { mapState } from "pinia";

import { useOnlineTagStore } from "@/stores/online-tag";

export default {
  name: "AdminSettingsButtonPrompts",
  computed: {
    ...mapState(useOnlineTagStore, ["pendingPrompts"]),
    hasPrompts() {
      return this.pendingPrompts.length > 0;
    },
  },
};
</script>

<style scoped lang="scss">
.promptDot {
  position: absolute;
  top: 6px;
  left: 6px;
  width: 10px;
  height: 10px;
  border-radius: 50%;
  background-color: rgb(var(--v-theme-warning));
  // Ring so the dot reads against the icon underneath.
  box-shadow: 0 0 0 2px rgb(var(--v-theme-surface));
  pointer-events: none;
}
</style>

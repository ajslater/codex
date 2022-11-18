<template>
  <v-toolbar
    id="titleBar"
    class="codexToolbar"
    :class="{ rightSpace }"
    density="compact"
  >
    <div id="buttonSpacer" />
    <v-spacer />
    <v-toolbar-title>Codex Administration</v-toolbar-title>
    <v-spacer />
    <SettingsDrawerButton
      :class="{ invisible: isSettingsDrawerOpen }"
      :disabled="isSettingsDrawerOpen"
      :plain="isSettingsDrawerOpen"
      @click="isSettingsDrawerOpen = true"
    />
  </v-toolbar>
</template>
<script>
import { mapWritableState } from "pinia";

import SettingsDrawerButton from "@/components/settings/button.vue";
import { useAdminStore } from "@/stores/admin";
export default {
  name: "AdminTitleToolbar",
  components: {
    SettingsDrawerButton,
  },
  computed: {
    ...mapWritableState(useAdminStore, ["isSettingsDrawerOpen"]),
    rightSpace() {
      return !this.$vuetify.display.mobile;
    },
  },
  mounted() {
    this.isSettingsDrawerOpen = !this.$vuetify.display.mobile;
  },
};
</script>

<style scoped lang="scss">
#buttonSpacer {
  width: 48px;
}
.invisible {
  visibility: hidden;
}
#titleBar {
  width: 100%;
  padding-top: env(safe-area-inset-top);
  padding-right: calc(env(safe-area-inset-right) / 2);
  padding-left: calc(env(safe-area-inset-left) / 2);
}
.rightSpace {
  width: calc(100% - 256px) !important;
}
</style>

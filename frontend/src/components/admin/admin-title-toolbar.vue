<template>
  <v-toolbar
    id="titleBar"
    class="codexToolbar"
    :class="{ rightSpace }"
    density="compact"
    elevation="8"
  >
    <div id="buttonSpacer" />
    <v-toolbar-title class="codexToolbarTitle">
      Codex Administration
    </v-toolbar-title>
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
import { useCommonStore } from "@/stores/common";
export default {
  name: "AdminTitleToolbar",
  components: {
    SettingsDrawerButton,
  },
  computed: {
    ...mapWritableState(useCommonStore, ["isSettingsDrawerOpen"]),
    rightSpace() {
      return !this.$vuetify.display.smAndDown;
    },
  },
  mounted() {
    this.isSettingsDrawerOpen = !this.$vuetify.display.smAndDown;
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
  top: 0px;
  width: 100%;
  padding-top: env(safe-area-inset-top);
  padding-right: calc(env(safe-area-inset-right) / 2);
  padding-left: calc(env(safe-area-inset-left) / 2);
}
.rightSpace {
  width: calc(100% - 256px) !important;
}
</style>

<template>
  <v-toolbar
    id="titleBar"
    class="codexToolbar"
    :class="{ drawerMargin: !$vuetify.display.mdAndDown }"
    density="compact"
    elevation="8"
  >
    <v-toolbar-title class="codexToolbarTitle">
      Codex Administration
    </v-toolbar-title>
    <SettingsDrawerButton
      :key="mobile"
      :class="{ invisible: !mobile }"
      :disabled="!mobile"
    />
  </v-toolbar>
</template>
<script>
import { mapActions } from "pinia";

import SettingsDrawerButton from "@/components/settings/button.vue";
import { useCommonStore } from "@/stores/common";
export default {
  name: "AdminTitleToolbar",
  components: {
    SettingsDrawerButton,
  },
  computed: {
    mobile() {
      return this.$vuetify.display.mobile;
    },
  },
  watch: {
    mobile(to) {
      if (!to) {
        this.setSettingsDrawerOpen(true);
      }
    },
  },
  methods: {
    ...mapActions(useCommonStore, ["setSettingsDrawerOpen"]),
  },
};
</script>

<style scoped lang="scss">
.invisible {
  visibility: hidden;
}
#titleBar {
  top: 0px;
  width: 100%;
  padding-top: env(safe-area-inset-top);
  padding-right: calc(env(safe-area-inset-right) / 2);
  padding-left: calc(48px + calc(env(safe-area-inset-left) / 2));
  z-index: 10;
}
.drawerMargin {
  width: calc(100% - 256px) !important;
}
</style>

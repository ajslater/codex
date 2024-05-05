<template>
  <v-toolbar
    id="titleBar"
    class="codexToolbar"
    :class="{ drawerMargin: !lgAndDown }"
    density="compact"
    elevation="8"
  >
    <v-toolbar-title class="codexToolbarTitle">
      Codex Administration
    </v-toolbar-title>
    <SettingsDrawerButton
      :key="lgAndDown"
      :class="{ invisible: !lgAndDown }"
      :disabled="!lgAndDown"
    />
  </v-toolbar>
</template>
<script>
import SettingsDrawerButton from "@/components/settings/button.vue";
export default {
  name: "AdminTitleToolbar",
  components: {
    SettingsDrawerButton,
  },
  computed: {
    lgAndDown() {
      return this.$vuetify.display.lgAndDown;
    },
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

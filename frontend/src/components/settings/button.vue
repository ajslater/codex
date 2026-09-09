<template>
  <ScaleButton
    id="settingsDrawerButton"
    variant="plain"
    icon
    title="Settings"
    @click.prevent="onClick"
  >
    <v-icon>
      {{ mdiMenu }}
    </v-icon>
    <component :is="AdminSettingsButtonProgress" v-if="isUserAdmin" />
    <component :is="AdminSettingsButtonErrors" v-if="isUserAdmin" />
    <component :is="AdminSettingsButtonPrompts" v-if="isUserAdmin" />
  </ScaleButton>
</template>

<script>
import { mdiMenu } from "@mdi/js";
import { mapActions, mapState } from "pinia";
import { defineAsyncComponent, markRaw } from "vue";

import ScaleButton from "@/components/scale-button.vue";
import { useAuthStore } from "@/stores/auth";
import { useCommonStore } from "@/stores/common";

const AdminSettingsButtonProgress = markRaw(
  defineAsyncComponent(
    () =>
      import("@/components/admin/drawer/admin-settings-button-progress.vue"),
  ),
);

const AdminSettingsButtonErrors = markRaw(
  defineAsyncComponent(
    () => import("@/components/admin/drawer/admin-settings-button-errors.vue"),
  ),
);

const AdminSettingsButtonPrompts = markRaw(
  defineAsyncComponent(
    () => import("@/components/admin/drawer/admin-settings-button-prompts.vue"),
  ),
);

export default {
  name: "SettingsDrawerButton",
  components: {
    AdminSettingsButtonErrors,
    AdminSettingsButtonProgress,
    AdminSettingsButtonPrompts,
    ScaleButton,
  },
  data() {
    return {
      mdiMenu,
      AdminSettingsButtonProgress,
      AdminSettingsButtonErrors,
      AdminSettingsButtonPrompts,
    };
  },
  computed: {
    ...mapState(useAuthStore, ["isUserAdmin"]),
  },
  methods: {
    ...mapActions(useCommonStore, ["setSettingsDrawerOpen"]),
    onClick() {
      this.setSettingsDrawerOpen(true);
    },
  },
};
</script>
<style scoped lang="scss">
#settingsDrawerButton {
  padding-right: max(10px, calc(env(safe-area-inset-right) / 2));
  /*
   * Vuetify 4.2 clips .v-btn (fix(variant) #22992). The admin librarian
   * progress ring is larger than the compact button box on xs, so without
   * this it loses its left and bottom arcs on phones.
   */
  overflow: visible;
}
</style>

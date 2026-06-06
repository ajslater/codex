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

export default {
  name: "SettingsDrawerButton",
  components: {
    AdminSettingsButtonErrors,
    AdminSettingsButtonProgress,
    ScaleButton,
  },
  data() {
    return {
      mdiMenu,
      AdminSettingsButtonProgress,
      AdminSettingsButtonErrors,
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
}
</style>

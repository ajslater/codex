<template>
  <v-btn v-bind="$attrs" icon title="Settings">
    <v-icon>
      {{ mdiMenu }}
    </v-icon>
    <component :is="AdminSettingsButtonProgress" v-if="isUserAdmin" />
  </v-btn>
</template>

<script>
import { mdiMenu } from "@mdi/js";
import { mapState } from "pinia";
import { defineAsyncComponent, markRaw } from "vue";

import { useAuthStore } from "@/stores/auth";

const AdminSettingsButtonProgress = markRaw(
  defineAsyncComponent(() =>
    import("@/components/admin/drawer/admin-settings-button-progress.vue")
  )
);

export default {
  name: "SettingsDrawerButton",
  data() {
    return {
      mdiMenu,
      AdminSettingsButtonProgress,
    };
  },
  computed: {
    ...mapState(useAuthStore, ["isUserAdmin"]),
  },
};
</script>

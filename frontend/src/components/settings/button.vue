<template>
  <v-btn v-bind="$attrs" icon ripple title="Settings">
    <component :is="AdminSettingsDrawerButtonIcon" v-if="isUserAdmin" />
    <v-icon v-else>
      {{ mdiMenu }}
    </v-icon>
  </v-btn>
</template>

<script>
import { mdiMenu } from "@mdi/js";
import { mapState } from "pinia";

import { useAuthStore } from "@/stores/auth";

const AdminSettingsDrawerButtonIcon = () =>
  import("@/components/admin/admin-settings-button-icon.vue");

export default {
  name: "SettingsDrawerButton",
  data() {
    return {
      mdiMenu,
      AdminSettingsDrawerButtonIcon,
    };
  },
  computed: {
    ...mapState(useAuthStore, {
      isUserAdmin: (state) => state.isUserAdmin,
    }),
  },
};
</script>

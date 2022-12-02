<template>
  <v-btn v-bind="$attrs" icon title="Settings">
    <component :is="AdminSettingsDrawerButtonIcon" v-if="isUserAdmin" />
    <v-icon v-else>
      {{ mdiMenu }}
    </v-icon>
  </v-btn>
</template>

<script>
import { mdiMenu } from "@mdi/js";
import { mapState } from "pinia";
import { defineAsyncComponent, markRaw } from "vue";

import { useAuthStore } from "@/stores/auth";

const AdminSettingsDrawerButtonIcon = markRaw(
  defineAsyncComponent(() =>
    import("@/components/admin/admin-settings-button-icon.vue")
  )
);

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

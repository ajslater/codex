<template>
  <v-btn icon title="Settings" @click.prevent="onClick">
    <v-icon>
      {{ mdiMenu }}
    </v-icon>
    <component :is="AdminSettingsButtonProgress" v-if="isUserAdmin" />
  </v-btn>
</template>

<script>
import { mdiMenu } from "@mdi/js";
import { mapActions, mapState } from "pinia";
import { defineAsyncComponent, markRaw } from "vue";

import { useAuthStore } from "@/stores/auth";
import { useCommonStore } from "@/stores/common";

const AdminSettingsButtonProgress = markRaw(
  defineAsyncComponent(
    () =>
      import("@/components/admin/drawer/admin-settings-button-progress.vue"),
  ),
);

export default {
  name: "SettingsDrawerButton",
  components: {
    AdminSettingsButtonProgress,
  },
  data() {
    return {
      mdiMenu,
      AdminSettingsButtonProgress,
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

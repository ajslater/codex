<template>
  <div v-if="isUserAdmin">
    <v-divider />
    <CodexListItem
      v-tooltip="{ openDelay: 2000, text: 'for updated comics' }"
      title="Poll All Libraries"
      :prepend-icon="mdiDatabaseClockOutline"
      @click="onPoll"
    />
    <CodexListItem
      v-if="showAdminPanelLink"
      class="adminPanelLink"
      :to="{ name: 'admin' }"
      :prepend-icon="mdiCrownOutline"
      title="Admin Panel"
      :append-icon="failedImportsIcon"
    />
    <AdminStatusList />
  </div>
</template>

<script>
import {
  mdiBookAlert,
  mdiCrownOutline,
  mdiDatabaseClockOutline,
  mdiOpenInNew,
} from "@mdi/js";
import { mapActions, mapState } from "pinia";

import AdminStatusList from "@/components/admin/drawer/status-list.vue";
import CodexListItem from "@/components/codex-list-item.vue";
import { useAdminStore } from "@/stores/admin";
import { useAuthStore } from "@/stores/auth";

export default {
  name: "AdminMenu",
  components: {
    AdminStatusList,
    CodexListItem,
  },
  data() {
    return {
      mdiOpenInNew,
      mdiDatabaseClockOutline,
      mdiCrownOutline,
    };
  },
  computed: {
    ...mapState(useAuthStore, ["isUserAdmin"]),
    ...mapState(useAdminStore, ["unseenFailedImports"]),
    failedImportsIcon() {
      return this.unseenFailedImports ? mdiBookAlert : undefined;
    },
    showAdminPanelLink() {
      return !this.$router.currentRoute?.value?.name?.startsWith("admin");
    },
  },
  methods: {
    ...mapActions(useAdminStore, ["clearFailedImports", "librarianTask"]),
    onPoll() {
      this.librarianTask("poll");
    },
  },
};
</script>

<style scoped lang="scss"></style>

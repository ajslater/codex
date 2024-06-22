<template>
  <div v-if="isUserAdmin">
    <v-divider />
    <DrawerItem
      v-tooltip="{ openDelay: 2000, text: 'for updated comics' }"
      title="Poll All Libraries"
      :prepend-icon="mdiDatabaseClockOutline"
      @click="onPoll"
    />
    <DrawerItem
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
import { mapActions, mapGetters, mapState } from "pinia";

import AdminStatusList from "@/components/admin/drawer/status-list.vue";
import DrawerItem from "@/components/drawer-item.vue";
import { useAdminStore } from "@/stores/admin";
import { useAuthStore } from "@/stores/auth";

export default {
  name: "AdminMenu",
  components: {
    AdminStatusList,
    DrawerItem,
  },
  data() {
    return {
      mdiOpenInNew,
      mdiDatabaseClockOutline,
      mdiCrownOutline,
    };
  },
  computed: {
    ...mapGetters(useAuthStore, ["isUserAdmin"]),
    ...mapState(useAdminStore, ["unseenFailedImports"]),
    showAdminPanelLink() {
      return !this.$router.currentRoute?.value?.name?.startsWith("admin");
    },
    failedImportsIcon() {
      return this.unseenFailedIimports ? mdiBookAlert : undefined;
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

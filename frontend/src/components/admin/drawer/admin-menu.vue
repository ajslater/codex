<template>
  <div v-if="isUserAdmin">
    <v-divider />
    <DrawerItem
      v-tooltip="{ openDelay: 2000, text: 'for updated comics' }"
      title="Poll All Libraries"
      :prepend-icon="mdiDatabaseClockOutline"
      @click="onPoll"
    />
    <div v-if="showAdminPanelLink">
      <v-list-item :to="{ name: 'admin' }">
        <v-list-item-title>
          <v-icon>{{ mdiCrownOutline }}</v-icon
          >Admin Panel
          <v-icon
            v-if="unseenFailedImports"
            id="failedImportsIcon"
            title="New Failed Imports"
          >
            {{ mdiBookAlert }}
          </v-icon>
        </v-list-item-title>
      </v-list-item>
    </div>
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
      mdiBookAlert,
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
  },
  methods: {
    ...mapActions(useAdminStore, ["clearFailedImports", "librarianTask"]),
    onPoll() {
      this.librarianTask("poll");
    },
  },
};
</script>

<style scoped lang="scss">
#failedImportsIcon {
  padding-left: 0.25em;
  color: rgb(var(--v-theme-error)) !important;
}
// Delaying title appearance works sometimes.
[title]:after{
  opacity: 0;
  transition: opacity 2s ease-in-out;
}
[title]:hover {
  opacity: 1;
}
</style>

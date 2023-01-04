<template>
  <div v-if="isUserAdmin">
    <div v-if="menu">
      <v-list-item @click="librarianTask('poll')">
        <v-list-item-title
          ><v-icon>{{ mdiDatabaseClockOutline }}</v-icon
          >Poll All Libraries</v-list-item-title
        >
      </v-list-item>
      <v-list-item :to="{ name: 'admin' }" @click="unseenFailedImports = false">
        <v-list-item-title>
          <v-icon>{{ mdiCogOutline }}</v-icon
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
  mdiCogOutline,
  mdiDatabaseClockOutline,
  mdiOpenInNew,
} from "@mdi/js";
import { mapActions, mapGetters, mapWritableState } from "pinia";

import AdminStatusList from "@/components/admin/drawer/status-list.vue";
import { useAdminStore } from "@/stores/admin";
import { useAuthStore } from "@/stores/auth";

export default {
  name: "AdminMenu",
  components: {
    AdminStatusList,
  },
  props: {
    menu: { type: Boolean, default: true },
  },
  data() {
    return {
      mdiBookAlert,
      mdiOpenInNew,
      mdiDatabaseClockOutline,
      mdiCogOutline,
    };
  },
  computed: {
    ...mapGetters(useAuthStore, ["isUserAdmin"]),
    ...mapWritableState(useAdminStore, ["unseenFailedImports"]),
  },
  methods: {
    ...mapActions(useAdminStore, ["clearFailedImports", "librarianTask"]),
  },
};
</script>

<style scoped lang="scss">
#failedImportsIcon {
  padding-left: 0.25em;
  color: rgb(var(--v-theme-error)) !important;
}
</style>

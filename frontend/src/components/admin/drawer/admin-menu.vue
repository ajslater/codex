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
    />
    <CodexListItem
      v-if="showTagWriteErrors"
      class="tagWriteErrorsLink"
      :to="{ name: 'admin-tagging', hash: '#tagging-errors' }"
      :prepend-icon="mdiAlertCircle"
      title="Tag Write Errors"
    />
    <CodexListItem
      v-if="showFailedImports"
      class="failedImportsLink"
      :to="{ name: 'admin-libraries', hash: '#failedImports' }"
      :prepend-icon="mdiBookAlert"
      title="Failed Imports"
    />
    <CodexListItem
      v-if="showPrompts"
      v-tooltip="{ openDelay: 2000, text: 'Review online tagging matches' }"
      class="promptsLink"
      :prepend-icon="mdiTagMultiple"
      :title="promptsLabel"
      @click="openPrompts"
    />
    <AdminStatusList />
  </div>
</template>

<script>
import {
  mdiAlertCircle,
  mdiBookAlert,
  mdiCrownOutline,
  mdiDatabaseClockOutline,
  mdiTagMultiple,
} from "@mdi/js";
import { mapActions, mapState, mapWritableState } from "pinia";

import AdminStatusList from "@/components/admin/drawer/status-list.vue";
import CodexListItem from "@/components/codex-list-item.vue";
import { useAdminStore } from "@/stores/admin";
import { useAuthStore } from "@/stores/auth";
import { useOnlineTagStore } from "@/stores/online-tag";

export default {
  name: "AdminMenu",
  components: {
    AdminStatusList,
    CodexListItem,
  },
  data() {
    return {
      mdiDatabaseClockOutline,
      mdiCrownOutline,
      mdiAlertCircle,
      mdiBookAlert,
      mdiTagMultiple,
    };
  },
  computed: {
    ...mapState(useAuthStore, ["isUserAdmin"]),
    ...mapState(useAdminStore, ["hasUnseenFailedImports", "tagWriteErrors"]),
    ...mapState(useOnlineTagStore, ["pendingPrompts"]),
    ...mapWritableState(useOnlineTagStore, ["promptDialogOpen"]),
    showTagWriteErrors() {
      return this.tagWriteErrors.length > 0;
    },
    showFailedImports() {
      return this.hasUnseenFailedImports;
    },
    showPrompts() {
      return this.pendingPrompts.length > 0;
    },
    promptsLabel() {
      const count = this.pendingPrompts.length;
      return `${count} Match${count === 1 ? "" : "es"} to Review`;
    },
    showAdminPanelLink() {
      return !this.$router.currentRoute?.value?.name?.startsWith("admin");
    },
  },
  created() {
    // Mirror the hamburger error-dot: load failed imports + the seen marker so
    // this menu reflects them even on admin tabs that don't fetch them.
    this.loadTable("FailedImport");
    this.loadFailedImportsSeen();
  },
  methods: {
    ...mapActions(useAdminStore, [
      "loadTable",
      "loadFailedImportsSeen",
      "librarianTask",
    ]),
    onPoll() {
      this.librarianTask("poll");
    },
    openPrompts() {
      // The OnlineTagPromptPopup (mounted in browser.vue + admin.vue) watches
      // this flag; flipping it opens the same Match Review dialog the browser
      // toolbar button does.
      this.promptDialogOpen = true;
    },
  },
};
</script>

<style scoped lang="scss">
// settings-drawer.vue forces every list-item icon to iconsInactive with
// !important; override it here (more specific + !important) so these
// notification icons carry their semantic color: red for errors/failed
// imports, amber for online-tagging matches to review.
.tagWriteErrorsLink :deep(.v-list-item__prepend .v-icon),
.failedImportsLink :deep(.v-list-item__prepend .v-icon) {
  color: rgb(var(--v-theme-error)) !important;
}

.promptsLink :deep(.v-list-item__prepend .v-icon) {
  color: rgb(var(--v-theme-warning)) !important;
}
</style>

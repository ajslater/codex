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
      :class="{ failedImportsUnseen: hasUnseenFailedImports }"
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
import { promptComics, useOnlineTagStore } from "@/stores/online-tag";

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
    ...mapState(useAdminStore, [
      "failedImports",
      "hasUnseenFailedImports",
      "tagWriteErrors",
    ]),
    ...mapState(useOnlineTagStore, ["pendingPrompts"]),
    ...mapWritableState(useOnlineTagStore, ["promptDialogOpen"]),
    showTagWriteErrors() {
      return this.tagWriteErrors.length > 0;
    },
    showFailedImports() {
      // Navigation, so it persists while there is anything to navigate
      // to. Gating it on *unseen* meant "Clear Warning" hid the way
      // back to a table that was still there, which is why the #854
      // reporter could not find it. The hamburger dot deliberately
      // stays on hasUnseenFailedImports: a dot is a notification, and
      // "seen" is the right thing for one.
      return Boolean(this.failedImports?.length);
    },
    showPrompts() {
      return this.pendingPrompts.length > 0;
    },
    promptsLabel() {
      // Comics, not questions: one question can hold a whole series, and the
      // Tagging tab counts the rows it will mark for review. A prompt that
      // names no comic at all still counts as one thing to look at, so a
      // malformed cache entry can't make a visible queue read as empty.
      const count = this.pendingPrompts.reduce(
        (total, prompt) => total + Math.max(promptComics(prompt).length, 1),
        0,
      );
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
// settings-drawer.vue tints every list-item icon icons-inactive; these
// override it so the notification icons carry their semantic color: red
// for errors/failed imports, amber for online-tagging matches to
// review. Both rules are in the same layer now, so the extra class here
// wins on specificity alone — no !important on either side.
// The failed-imports link now outlives the warning, so only the unseen
// state is colored; once cleared it reads as ordinary navigation.

/* Layered: these rules beat Vuetify's component CSS by position,
 * and lose to a `color`/utility prop, which is the intended order. */
@layer codex-components {
  .tagWriteErrorsLink :deep(.v-list-item__prepend .v-icon),
  .failedImportsUnseen :deep(.v-list-item__prepend .v-icon) {
    color: rgb(var(--v-theme-error));
  }

  .promptsLink :deep(.v-list-item__prepend .v-icon) {
    color: rgb(var(--v-theme-warning));
  }
}
</style>

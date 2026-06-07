<!--
  A red dot overlaid on the settings (hamburger) button when tag-write errors
  or failed imports are waiting for an admin. Mirrors
  admin-settings-button-progress.vue's absolute-overlay convention. Loads both
  lists on creation so the badge reflects state persisted on the server across
  restarts. One dot covers both error kinds (same color, same corner); the
  sidebar admin menu disambiguates them with separate list items.
-->
<template>
  <span
    v-if="hasErrors"
    class="errorDot"
    title="Tag write errors or failed imports"
  />
</template>

<script>
import { mapActions, mapState } from "pinia";

import { useAdminStore } from "@/stores/admin";

export default {
  name: "AdminSettingsButtonErrors",
  computed: {
    ...mapState(useAdminStore, [
      "tagWriteErrors",
      "failedImports",
      "failedImportsDismissed",
    ]),
    hasErrors() {
      return (
        this.tagWriteErrors.length > 0 ||
        (this.failedImports.length > 0 && !this.failedImportsDismissed)
      );
    },
  },
  created() {
    this.loadTagWriteErrors();
    this.loadTable("FailedImport");
  },
  methods: {
    ...mapActions(useAdminStore, ["loadTagWriteErrors", "loadTable"]),
  },
};
</script>

<style scoped lang="scss">
.errorDot {
  position: absolute;
  top: 6px;
  right: 6px;
  width: 10px;
  height: 10px;
  border-radius: 50%;
  background-color: rgb(var(--v-theme-error));
  // Ring so the dot reads against the icon underneath.
  box-shadow: 0 0 0 2px rgb(var(--v-theme-surface));
  pointer-events: none;
}
</style>

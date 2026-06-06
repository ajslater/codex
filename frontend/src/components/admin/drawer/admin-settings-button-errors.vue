<!--
  A red dot overlaid on the settings (hamburger) button when tag-write errors
  are waiting for an admin. Mirrors admin-settings-button-progress.vue's
  absolute-overlay convention. Loads the error list on creation so the badge
  reflects errors persisted in the server cache across restarts.
-->
<template>
  <span v-if="hasErrors" class="errorDot" title="Tag write errors" />
</template>

<script>
import { mapActions, mapState } from "pinia";

import { useAdminStore } from "@/stores/admin";

export default {
  name: "AdminSettingsButtonErrors",
  computed: {
    ...mapState(useAdminStore, ["tagWriteErrors"]),
    hasErrors() {
      return this.tagWriteErrors.length > 0;
    },
  },
  created() {
    this.loadTagWriteErrors();
  },
  methods: {
    ...mapActions(useAdminStore, ["loadTagWriteErrors"]),
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

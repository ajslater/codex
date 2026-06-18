<!--
  Bottom-of-Tagging-tab panel listing comics that failed to have their tags
  written (read-only mount, permission error, …). Errors live in the server's
  filesystem cache, not the database; the admin clears them here. The
  ``#tagging-errors`` anchor is the deep-link target from the sidebar drawer.
-->
<template>
  <div v-if="showErrors" id="tagging-errors" class="tagWriteErrors">
    <AdminSection title="Tag Write Errors">
      <template #actions>
        <span class="errorCount">
          <v-icon :icon="mdiAlertCircle" size="small" class="errorIcon" />
          {{ tagWriteErrors.length }}
        </span>
        <ConfirmDialog
          button-text="Clear"
          title-text="Clear Tag Write Errors"
          text="Remove all collected tag write errors?"
          confirm-text="Clear"
          variant="text"
          size="small"
          :block="false"
          @confirm="clearTagWriteErrors"
        />
      </template>
      <template #hint>
        These comics failed to have their tags written — usually because the
        comics directory is mounted read-only or Codex lacks permission to write
        to it. Fix the filesystem permissions, then edit the tags again.
      </template>
      <v-table id="tagWriteErrorsTable" striped="odd">
        <template #default>
          <thead>
            <tr>
              <th>Path</th>
              <th>Time</th>
              <th>Error</th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="item in tagWriteErrors" :key="`twe:${item.path}`">
              <td class="pathCol">
                {{ item.path }}
              </td>
              <td class="dateCol">
                <DateTimeColumn :dttm="item.time" />
              </td>
              <td class="errorCol">
                {{ item.error }}
              </td>
            </tr>
          </tbody>
        </template>
      </v-table>
    </AdminSection>
  </div>
</template>

<script>
import { mdiAlertCircle } from "@mdi/js";
import { mapActions, mapState } from "pinia";

import AdminSection from "@/components/admin/tabs/admin-section.vue";
import DateTimeColumn from "@/components/admin/tabs/datetime-column.vue";
import ConfirmDialog from "@/components/confirm-dialog.vue";
import { useAdminStore } from "@/stores/admin";

export default {
  name: "AdminTagWriteErrorsPanel",
  components: {
    AdminSection,
    ConfirmDialog,
    DateTimeColumn,
  },
  data() {
    return {
      mdiAlertCircle,
    };
  },
  computed: {
    ...mapState(useAdminStore, {
      tagWriteErrors: (state) => state.tagWriteErrors,
      showErrors: (state) =>
        state.tagWriteErrors && state.tagWriteErrors.length > 0,
    }),
  },
  watch: {
    // Re-scroll if the deep link fires while already on the Tagging tab.
    "$route.hash"() {
      this.maybeScroll();
    },
    // The panel mounts only once errors load; scroll once it appears.
    showErrors(isShown) {
      if (isShown) this.maybeScroll();
    },
  },
  mounted() {
    this.maybeScroll();
  },
  methods: {
    ...mapActions(useAdminStore, ["clearTagWriteErrors"]),
    maybeScroll() {
      if (this.$route.hash !== "#tagging-errors") return;
      this.$nextTick(() => {
        const el = document.getElementById("tagging-errors");
        if (el) el.scrollIntoView({ behavior: "smooth", block: "start" });
      });
    },
  },
};
</script>

<style scoped lang="scss">
@use "@/components/admin/tabs/design.scss" as d;

.tagWriteErrors {
  margin-top: d.$space-4;
}

.errorCount {
  margin-right: d.$space-2;
  color: rgb(var(--v-theme-error));
}

.errorIcon {
  color: rgb(var(--v-theme-error));
}

#tagWriteErrorsTable {
  background-color: inherit;
}

.pathCol {
  word-break: break-all;
}

.errorCol {
  color: rgb(var(--v-theme-textSecondary));
}
</style>

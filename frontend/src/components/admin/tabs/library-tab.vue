<template>
  <div>
    <header class="tabHeader">
      <AdminCreateUpdateDialog
        table="Library"
        :inputs="AdminLibraryCreateUpdateInputs"
      />
    </header>
    <AdminTable
      :headers="headers"
      :items="libraries"
      :sort-by="[{ key: 'path', order: 'asc' }]"
    >
      <template #no-data>
        <td class="adminNoData" colspan="100%">
          Add a Library to start using Codex
        </td>
      </template>
      <template #[`item.events`]="{ item }">
        <v-checkbox-btn :model-value="item.events" disabled />
      </template>
      <template #[`item.poll`]="{ item }">
        <v-checkbox-btn :model-value="item.poll" disabled />
      </template>
      <template #[`item.pollEvery`]="{ item }">
        <span :class="{ disabled: !item.poll }">
          {{ item.pollEvery }}
        </span>
      </template>
      <template #[`item.lastPoll`]="{ item }">
        <DateTimeColumn :dttm="item.lastPoll" />
      </template>
      <template #[`item.groups`]="{ item }">
        <RelationChips
          :pks="item.groups"
          :objs="groups"
          group-type
          title-key="name"
        />
      </template>
      <template #[`item.actions`]="{ item }">
        <ConfirmDialog
          :icon="mdiDatabaseClockOutline"
          title-text="Poll for updated comics"
          :object-name="item.path"
          confirm-text="Poll Library"
          size="small"
          density="compact"
          @confirm="poll(item.pk)"
        />
        <ConfirmDialog
          :icon="mdiDatabaseSyncOutline"
          title-text="Force update every comic"
          :object-name="item.path"
          confirm-text="Force Update"
          size="small"
          density="compact"
          @confirm="forcePoll(item.pk)"
        />
        <AdminCreateUpdateDialog
          table="Library"
          :old-row="item"
          :inputs="AdminLibraryCreateUpdateInputs"
          max-width="22em"
          size="small"
          density="compact"
        />
        <AdminDeleteRowDialog
          table="Library"
          :pk="item.pk"
          :name="item.path"
          size="small"
          density="compact"
        />
      </template>
    </AdminTable>
    <v-expand-transition>
      <AdminFailedImportsPanel />
    </v-expand-transition>
  </div>
</template>

<script>
import {
  mdiDatabaseClockOutline,
  mdiDatabaseSyncOutline,
  mdiOpenInNew,
} from "@mdi/js";
import { mapActions, mapState } from "pinia";
import { markRaw } from "vue";

import AdminCreateUpdateDialog from "@/components/admin/create-update-dialog/create-update-dialog.vue";
import AdminLibraryCreateUpdateInputs from "@/components/admin/create-update-dialog/library-create-update-inputs.vue";
import AdminTable from "@/components/admin/tabs/admin-table.vue";
import DateTimeColumn from "@/components/admin/tabs/datetime-column.vue";
import AdminDeleteRowDialog from "@/components/admin/tabs/delete-row-dialog.vue";
import AdminFailedImportsPanel from "@/components/admin/tabs/failed-imports-panel.vue";
import RelationChips from "@/components/admin/tabs/relation-chips.vue";
import ConfirmDialog from "@/components/confirm-dialog.vue";
import { getDateTime } from "@/datetime";
import { useAdminStore } from "@/stores/admin";
import { useBrowserStore } from "@/stores/browser";

export default {
  name: "AdminLibrariesTab",
  components: {
    AdminTable,
    AdminDeleteRowDialog,
    AdminFailedImportsPanel,
    AdminCreateUpdateDialog,
    RelationChips,
    ConfirmDialog,
    DateTimeColumn,
  },
  data() {
    return {
      lastUpdate: {
        pk: 0,
        field: undefined,
      },
      mdiDatabaseClockOutline,
      mdiDatabaseSyncOutline,
      mdiOpenInNew,
      AdminLibraryCreateUpdateInputs: markRaw(AdminLibraryCreateUpdateInputs),
      headers: [
        { title: "Path", key: "path", align: "start" },
        {
          title: "Watch File Events",
          key: "events",
        },
        {
          title: "Poll Files Periodically",
          key: "poll",
        },
        { title: "Poll Every", key: "pollEvery" },
        { title: "Last Poll", key: "lastPoll" },
        { title: "Groups", key: "groups" },
        { title: "Actions", key: "actions", sortable: false },
      ],
    };
  },
  computed: {
    ...mapState(useAdminStore, {
      groups: (state) => state.groups,
      libraries: (state) => state.libraries,
      formErrors: (state) => state.form.errors,
    }),
    ...mapState(useBrowserStore, {
      twentyFourHourTime: (state) => state.settings.twentyFourHourTime,
    }),
  },
  mounted() {
    this.loadTables(["Group", "Library", "FailedImport"]);
  },
  methods: {
    ...mapActions(useAdminStore, [
      "updateRow",
      "clearErrors",
      "librarianTask",
      "loadTables",
    ]),
    formatDateTime: (dttm) => {
      return dttm ? getDateTime(dttm, this.twentyFourHourTime) : "";
    },
    changeCol(pk, field, val) {
      this.lastUpdate.pk = pk;
      this.lastUpdate.field = field;
      const data = { [field]: val };
      this.updateRow("Library", pk, data);
    },
    getFormErrors(pk, field) {
      if (pk === this.lastUpdate.pk && field === this.lastUpdate.field) {
        return this.formErrors;
      }
    },
    poll(pk) {
      this.librarianTask("poll", `Poll Library ${pk}`, pk);
    },
    forcePoll(pk) {
      this.librarianTask("poll_force", `Force Poll Library ${pk}`, pk);
    },
  },
};
</script>
<style scoped lang="scss">
.disabled {
  color: rgb(var(--v-theme-textDisabled)) !important;
}
</style>

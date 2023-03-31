<template>
  <div>
    <header class="tabHeader">
      <AdminCreateUpdateDialog
        table="Library"
        :inputs="AdminLibraryCreateUpdateInputs"
      />
    </header>
    <v-data-table-virtual
      class="adminTable"
      fixed-headers
      item-value="pk"
      item-title="path"
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
        <v-checkbox-btn :model-value="item.raw.events" disabled />
      </template>
      <template #[`item.poll`]="{ item }">
        <v-checkbox-btn :model-value="item.raw.poll" disabled />
      </template>
      <template #[`item.lastPoll`]="{ item }">
        <DateTimeColumn :dttm="item.raw.lastPoll" />
      </template>
      <template #[`item.groups`]="{ item }">
        <RelationChips :pks="item.raw.groups" :map="groupMap" />
      </template>
      <template #[`item.actions`]="{ item }">
        <ConfirmDialog
          :icon="mdiDatabaseClockOutline"
          title-text="Poll for updated comics in"
          :object-name="item.raw.path"
          confirm-text="Poll Library"
          size="small"
          density="compact"
          @confirm="poll(item.raw.pk)"
        />
        <ConfirmDialog
          :icon="mdiDatabaseImportOutline"
          title-text="Force update every comic in"
          :object-name="item.raw.path"
          confirm-text="Force Update"
          size="small"
          density="compact"
          @confirm="forcePoll(item.raw.pk)"
        />
        <AdminCreateUpdateDialog
          table="Library"
          :old-row="item.raw"
          :inputs="AdminLibraryCreateUpdateInputs"
          max-width="22em"
          size="small"
          density="compact"
        />
        <AdminDeleteRowDialog
          table="Library"
          :pk="item.raw.pk"
          :name="item.raw.path"
          size="small"
          density="compact"
        />
      </template>
    </v-data-table-virtual>
    <v-expand-transition>
      <AdminFailedImportsPanel />
    </v-expand-transition>
  </div>
</template>

<script>
import {
  mdiDatabaseClockOutline,
  mdiDatabaseImportOutline,
  mdiOpenInNew,
} from "@mdi/js";
import { mapActions, mapGetters, mapState } from "pinia";
import { markRaw } from "vue";
import { VDataTableVirtual } from "vuetify/labs/components";

import AdminCreateUpdateDialog from "@/components/admin/create-update-dialog.vue";
import DateTimeColumn from "@/components/admin/datetime-column.vue";
import AdminDeleteRowDialog from "@/components/admin/delete-row-dialog.vue";
import AdminFailedImportsPanel from "@/components/admin/failed-imports-panel.vue";
import AdminLibraryCreateUpdateInputs from "@/components/admin/library-create-update-inputs.vue";
import RelationChips from "@/components/admin/relation-chips.vue";
import ConfirmDialog from "@/components/confirm-dialog.vue";
import { getDateTime } from "@/datetime";
import { useAdminStore } from "@/stores/admin";
import { useBrowserStore } from "@/stores/browser";

export default {
  name: "AdminLibrariesTab",
  components: {
    VDataTableVirtual,
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
      mdiDatabaseImportOutline,
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
    ...mapGetters(useAdminStore, ["groupMap"]),
    ...mapState(useAdminStore, {
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
      if (!dttm) {
        return "";
      }
      return getDateTime(dttm, this.twentyFourHourTime);
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

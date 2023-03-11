<template>
  <div>
    <header class="tabHeader">
      <AdminCreateUpdateDialog
        table="Library"
        :inputs="AdminLibraryCreateUpdateInputs"
        width="100%"
      />
    </header>
    <VDataTableVirtual
      fixed-headers
      item-value="pk"
      item-title="path"
      :headers="headers"
      :items="libraries"
      :sort-by="[{ key: 'path', order: 'asc' }]"
    >
      <template #no-data> Add a Library to start using Codex </template>
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
        <v-btn
          rounded
          icon
          density="compact"
          size="small"
          title="Poll Library Now"
          @click="poll(item.raw.pk)"
        >
          <v-icon>{{ mdiDatabaseClockOutline }}</v-icon>
        </v-btn>
        <ConfirmDialog
          :icon="mdiDatabaseImportOutline"
          title-text="Force Reimport of Entire Library"
          :object-name="item.raw.path"
          confirm-text="Force Reimport"
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
    </VDataTableVirtual>
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

const FAILED_IMPORTS_HEIGHT = 60 + 48 + 64;

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
      FAILED_IMPORTS_HEIGHT,
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
        { title: "Watch Filesystem Events", key: "events", width: 130 },
        { title: "Poll Filesystem Periodically", key: "poll", width: 130 },
        { title: "Poll Every", key: "pollEvery", width: 130 },
        { title: "Last Poll", key: "lastPoll", width: 120 },
        { title: "Groups", key: "groups" },
        { title: "Actions", key: "actions", width: 112, sortable: false },
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

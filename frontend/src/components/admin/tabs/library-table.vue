<template>
  <AdminTable :headers="headers">
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
      <span class="actionButtonCell">
        <ConfirmDialog
          :icon="mdiDatabaseClockOutline"
          :title-text="`Poll for updated ${itemName}s`"
          :text="item.path"
          :confirm-text="pollConfirmText(item)"
          :size="iconSize"
          density="compact"
          @confirm="poll(item)"
        />
        <ConfirmDialog
          :icon="mdiDatabaseSyncOutline"
          :title-text="`Force update every ${itemName}`"
          :text="item.path"
          confirm-text="Force Update"
          :size="iconSize"
          density="compact"
          @confirm="forcePoll(item)"
        />
        <AdminCreateUpdateDialog
          table="Library"
          :old-row="item"
          :inputs="AdminLibraryCreateUpdateInputs"
          :label="updateLabel"
          max-width="22em"
          :size="iconSize"
          density="compact"
        />
        <AdminDeleteRowDialog
          v-if="!item.coversOnly"
          table="Library"
          :pk="item.pk"
          :name="item.path"
          :size="iconSize"
          density="compact"
        />
      </span>
    </template>
  </AdminTable>
</template>

<script>
import {
  mdiCircleOffOutline,
  mdiDatabaseClockOutline,
  mdiDatabaseSyncOutline,
  mdiOpenInNew,
} from "@mdi/js";
import { mapActions, mapGetters, mapState } from "pinia";
import { markRaw } from "vue";

import AdminCreateUpdateDialog from "@/components/admin/create-update-dialog/create-update-dialog.vue";
import AdminLibraryCreateUpdateInputs from "@/components/admin/create-update-dialog/library-create-update-inputs.vue";
import AdminTable from "@/components/admin/tabs/admin-table.vue";
import DateTimeColumn from "@/components/admin/tabs/datetime-column.vue";
import AdminDeleteRowDialog from "@/components/admin/tabs/delete-row-dialog.vue";
import RelationChips from "@/components/admin/tabs/relation-chips.vue";
import ConfirmDialog from "@/components/confirm-dialog.vue";
import { getDateTime } from "@/datetime";
import { useAdminStore } from "@/stores/admin";
import { useBrowserStore } from "@/stores/browser";
import { useCommonStore } from "@/stores/common";

export default {
  name: "AdminLibrariesTab",
  components: {
    AdminTable,
    AdminDeleteRowDialog,
    AdminCreateUpdateDialog,
    RelationChips,
    ConfirmDialog,
    DateTimeColumn,
  },
  props: {
    coversDir: { type: Boolean, default: false },
  },
  data() {
    return {
      lastUpdate: {
        pk: 0,
        field: undefined,
      },
      mdiCircleOffOutline,
      mdiDatabaseClockOutline,
      mdiDatabaseSyncOutline,
      mdiOpenInNew,
      AdminLibraryCreateUpdateInputs: markRaw(AdminLibraryCreateUpdateInputs),
    };
  },
  computed: {
    ...mapGetters(useAdminStore, ["normalLibraries", "customCoverLibraries"]),
    ...mapState(useAdminStore, {
      groups: (state) => state.groups,
    }),
    ...mapState(useCommonStore, {
      formErrors: (state) => state.form?.errors,
    }),
    ...mapState(useBrowserStore, {
      twentyFourHourTime: (state) => state.settings.twentyFourHourTime,
    }),
    headers() {
      const headers = [
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
      ];
      if (!this.coversDir) {
        headers.push({ title: "Groups", key: "groups" });
      }
      headers.push({ title: "Actions", key: "actions", sortable: false });
      return headers;
    },
    items() {
      return self.coversDir ? this.customCoverLibraries : this.normalLibraries;
    },
    updateLabel() {
      return this.coversDir ? "Cover Dir" : "";
    },
    itemName() {
      return this.coversDir ? "custom covers" : "comics";
    },
    iconSize() {
      const display = this.$vuetify.display;
      if (display.xlAndUp) {
        return "x-large";
      } else if (display.lgAndUp) {
        return "large";
      } else if (display.mdAndUp) {
        return "default";
      } else {
        return "small";
      }
    },
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
    formatDateTime(dttm) {
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
    libraryLabel(item, long = true) {
      let label = "";
      if (item.coversOnly) {
        if (long) {
          label += "Custom Group ";
        }
        label += "Cover Dir";
      } else {
        label += "Library";
      }
      return label;
    },
    poll(item) {
      const label = this.libraryLabel(item);
      this.librarianTask("poll", `Poll ${label} ${item.pk}`, item.pk);
    },
    forcePoll(item) {
      const label = this.libraryLabel(item);
      this.librarianTask(
        "poll_force",
        `Force Poll ${label} ${item.pk}`,
        item.pk,
      );
    },
    pollConfirmText(item) {
      const label = this.libraryLabel(item, false);
      return `Poll ${label}`;
    },
  },
};
</script>
<style scoped lang="scss">
.disabled {
  color: rgb(var(--v-theme-textDisabled)) !important;
}

.actionButtonCell :deep(> button) {
  opacity: 0.7;
}

.actionButtonCell :deep(> button:hover) {
  opacity: 1;
}
</style>

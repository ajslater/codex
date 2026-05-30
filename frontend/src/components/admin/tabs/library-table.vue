<template>
  <AdminTable :headers="headers">
    <template #no-data>
      <td class="adminNoData" colspan="100%">
        Add a Library to start using Codex
      </td>
    </template>
    <template #[`item.comicCount`]="{ item }">
      {{ formatNumber(item.comicCount) }}
    </template>
    <template v-if="isFailedImports" #[`item.failedCount`]="{ item }">
      <span :class="failedComicsClasses(item)">
        {{ formatNumber(item.failedCount) }}
      </span>
    </template>
    <template #[`item.events`]="{ item }">
      <v-checkbox-btn :model-value="item.events" disabled />
    </template>
    <template #[`item.poll`]="{ item }">
      <v-checkbox-btn :model-value="item.poll" disabled />
    </template>
    <template #[`item.pollEvery`]="{ item }">
      <span :class="{ disabled: !item.poll }">
        {{ removeSeconds(item.pollEvery) }}
      </span>
    </template>
    <template #[`item.lastPoll`]="{ item }">
      <DateTimeColumn :dttm="item.lastPoll" />
    </template>
    <template v-if="isGroups" #[`item.groups`]="{ item }">
      <RelationChips
        :pks="item.groups"
        :objs="groups"
        group-type
        title-key="name"
      />
    </template>
    <template #[`item.actions`]="{ item }">
      <span class="adminActionCell">
        <ConfirmDialog
          :icon="mdiDatabaseClockOutline"
          title-text="Poll for updated comics"
          :text="item.path"
          confirm-text="Poll Library"
          :size="iconSize"
          density="compact"
          @confirm="poll(item)"
        />
        <ConfirmDialog
          :icon="mdiDatabaseSyncOutline"
          title-text="Force update comics"
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
          max-width="22em"
          :size="iconSize"
          density="compact"
        />
        <AdminDeleteRowDialog
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
import { mapActions, mapState } from "pinia";
import { markRaw } from "vue";

import AdminCreateUpdateDialog from "@/components/admin/create-update-dialog/create-update-dialog.vue";
import AdminLibraryCreateUpdateInputs from "@/components/admin/create-update-dialog/library-create-update-inputs.vue";
import AdminTable from "@/components/admin/tabs/admin-table.vue";
import DateTimeColumn from "@/components/admin/tabs/datetime-column.vue";
import AdminDeleteRowDialog from "@/components/admin/tabs/delete-row-dialog.vue";
import RelationChips from "@/components/admin/tabs/relation-chips.vue";
import ConfirmDialog from "@/components/confirm-dialog.vue";
import { NUMBER_FORMAT } from "@/datetime";
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
    ...mapState(useAdminStore, {
      groups: (state) => state.groups,
      isFailedImports: (state) => Boolean(state?.failedImports?.length),
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
        { title: "Comics", key: "comicCount" },
      ];
      if (this.isFailedImports) {
        headers.push({ title: "Failed", key: "failedCount" });
      }
      headers.push(
        ...[
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
        ],
      );
      if (this.isGroups) {
        headers.push({ title: "Groups", key: "groups" });
      }
      headers.push({ title: "Actions", key: "actions", sortable: false });
      return headers;
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
    isGroups() {
      return Boolean(this.groups?.length);
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
    formatNumber(num) {
      return NUMBER_FORMAT.format(num);
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
    poll(item) {
      this.librarianTask("poll", `Poll Library ${item.pk}`, item.pk);
    },
    forcePoll(item) {
      this.librarianTask(
        "poll_force",
        `Force Poll Library ${item.pk}`,
        item.pk,
      );
    },
    failedComicsClasses(item) {
      const classes = {};
      if (item?.failedCount) {
        classes["failedComics"] = true;
      }
      return classes;
    },
    removeSeconds(duration) {
      return duration.slice(0, -3);
    },
  },
};
</script>
<style scoped lang="scss">
@use "@/components/admin/tabs/admin-section.scss";

.disabled {
  color: rgb(var(--v-theme-textDisabled)) !important;
}

.failedComics {
  color: rgb(var(--v-theme-error));
}
</style>

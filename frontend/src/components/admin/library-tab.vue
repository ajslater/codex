<template>
  <div>
    <header class="tabHeader">
      <AdminCreateUpdateDialog
        table="Library"
        :inputs="AdminLibraryCreateUpdateInputs"
        max-width="22em"
      />
    </header>
    <v-table
      class="highlight-table admin-table"
      fixed-header
      :height="tableHeight"
    >
      <template #default>
        <thead>
          <tr>
            <th>Path</th>
            <th>Watch Filesystem Events</th>
            <th>Poll Filesystem Periodically</th>
            <th>Poll Every</th>
            <th>Last Poll</th>
            <th>Groups</th>
            <th>Poll for Updates Now</th>
            <th>Force Reimport</th>
            <th>Edit</th>
            <th>Delete</th>
          </tr>
        </thead>
        <tbody :style="tbodyStyle">
          <tr v-for="item in libraries" :key="item.pk">
            <td>{{ item.path }}</td>
            <td>
              <v-checkbox
                class="tableCheckbox"
                :model-value="item.events"
                density="compact"
                disabled
              />
            </td>
            <td>
              <v-checkbox
                class="tableCheckbox"
                :model-value="item.poll"
                density="compact"
                disabled
              />
            </td>
            <td class="pollEveryCol" :class="{ disabled: !item.poll }">
              {{ item.pollEvery }}
            </td>
            <td class="dateCol">
              <DateTimeColumn :dttm="item.lastPoll" />
            </td>
            <td>
              <RelationChips :pks="item.groups" :map="groupMap" />
            </td>
            <td>
              <v-btn icon @click="poll(item.pk)">
                <v-icon>{{ mdiDatabaseClockOutline }}</v-icon>
              </v-btn>
            </td>
            <td>
              <ConfirmDialog
                :icon="mdiDatabaseImportOutline"
                title-text="Force Reimport of Entire Library"
                :object-name="item.path"
                confirm-text="Force Reimport"
                @confirm="forcePoll(item.pk)"
              />
            </td>
            <td>
              <AdminCreateUpdateDialog
                table="Library"
                :old-row="item"
                :inputs="AdminLibraryCreateUpdateInputs"
                max-width="22em"
              />
            </td>
            <td>
              <AdminDeleteRowDialog
                table="Library"
                :pk="item.pk"
                :name="item.path"
              />
            </td>
          </tr>
        </tbody>
      </template>
    </v-table>
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

const FIXED_TOOLBARS = 96 + 16;
const ADD_HEADER = 36;
const TABLE_PADDING = 24;
const FAILED_IMPORTS = 60 + 48 + 64;
const BUFFER = FIXED_TOOLBARS + ADD_HEADER + FAILED_IMPORTS + TABLE_PADDING;
const TABLE_ROW_HEIGHT = 48;
const MIN_TABLE_HEIGHT = TABLE_ROW_HEIGHT * 2;
const ROW_HEIGHT = 84;

export default {
  name: "AdminLibrariesTab",
  components: {
    AdminDeleteRowDialog,
    AdminFailedImportsPanel,
    AdminCreateUpdateDialog,
    RelationChips,
    ConfirmDialog,
    DateTimeColumn,
  },
  props: {
    innerHeight: {
      type: Number,
      required: true,
    },
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
    };
  },
  computed: {
    ...mapGetters(useAdminStore, ["groupMap"]),
    ...mapState(useAdminStore, {
      libraries: (state) => state.libraries,
      formErrors: (state) => state.form.errors,
      tableMaxHeight: (state) =>
        (state.libraries.length + 1) * TABLE_ROW_HEIGHT,
    }),
    ...mapState(useBrowserStore, {
      twentyFourHourTime: (state) => state.settings.twentyFourHourTime,
    }),
    tableHeight() {
      const availableHeight = this.innerHeight - BUFFER;
      return this.tableMaxHeight < availableHeight
        ? undefined
        : Math.max(availableHeight, MIN_TABLE_HEIGHT);
    },
    tbodyStyle() {
      return this.libraries
        ? { height: ROW_HEIGHT * this.libraries.length + "px" }
        : {};
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

<style scoped lang="scss">
.pollEveryCol {
  min-width: 9em;
}
.dateCol {
  min-width: 8em;
}
.disabled {
  color: rgb(var(--v-theme-textDisabled));
}
</style>

<template>
  <div>
    <header class="tabHeader">
      <AdminLibraryCreateUpdateDialog />
    </header>
    <v-simple-table
      class="highlight-simple-table admin-table"
      fixed-header
      :height="tableHeight"
    >
      <template #default>
        <thead>
          <tr>
            <th>Path</th>
            <th>Watch Filesystem Events</th>
            <th>Poll Filesystem</th>
            <th>Poll Every</th>
            <th>Last Poll</th>
            <th>Groups</th>
            <th>Poll for Updates Now</th>
            <th>Force Update</th>
            <th>Edit</th>
            <th>Delete</th>
          </tr>
        </thead>
        <tbody>
          <tr v-for="item in libraries" :key="item.id">
            <td>{{ item.path }}</td>
            <td>
              <v-simple-checkbox :value="item.events" dense disabled />
            </td>
            <td>
              <v-simple-checkbox :value="item.poll" dense disabled />
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
              <v-btn icon ripple @click="poll(item.id)">
                <v-icon>{{ mdiDatabaseClockOutline }}</v-icon>
              </v-btn>
            </td>
            <td>
              <AdminTaskConfirmDialog
                :task="{
                  icon: true,
                  text: `Force Update ${item.path}`,
                  confirm: 'This can take a long time',
                }"
                @confirm="forcePoll(item.id)"
              />
            </td>
            <td>
              <AdminLibraryCreateUpdateDialog
                :update="true"
                :old-library="item"
              />
            </td>
            <td>
              <AdminDeleteRowDialog
                table="Library"
                :pk="item.id"
                :name="item.path"
              />
            </td>
          </tr>
        </tbody>
      </template>
    </v-simple-table>
    <v-expand-transition>
      <AdminFailedImportsPanel />
    </v-expand-transition>
  </div>
</template>

<script>
import { mdiDatabaseClockOutline, mdiOpenInNew } from "@mdi/js";
import { mapActions, mapGetters, mapState } from "pinia";

import DateTimeColumn from "@/components/admin/datetime-column.vue";
import AdminDeleteRowDialog from "@/components/admin/delete-row-dialog.vue";
import AdminFailedImportsPanel from "@/components/admin/failed-imports-panel.vue";
import AdminLibraryCreateUpdateDialog from "@/components/admin/library-create-update-dialog.vue";
import RelationChips from "@/components/admin/relation-chips.vue";
import AdminTaskConfirmDialog from "@/components/admin/task-dialog.vue";
import { DATETIME_FORMAT } from "@/datetime";
import { useAdminStore } from "@/stores/admin";

const FIXED_TOOLBARS = 96 + 16;
const ADD_HEADER = 36;
const TABLE_PADDING = 24;
const FAILED_IMPORTS = 60 + 48 + 64;
const BUFFER = FIXED_TOOLBARS + ADD_HEADER + FAILED_IMPORTS + TABLE_PADDING;
const TABLE_ROW_HEIGHT = 48;
const MIN_TABLE_HEIGHT = TABLE_ROW_HEIGHT * 2;

export default {
  name: "AdminLibrariesPanel",
  components: {
    AdminDeleteRowDialog,
    AdminFailedImportsPanel,
    AdminLibraryCreateUpdateDialog,
    RelationChips,
    AdminTaskConfirmDialog,
    DateTimeColumn,
  },
  data() {
    return {
      lastUpdate: {
        pk: 0,
        field: undefined,
      },
      mdiDatabaseClockOutline,
      mdiOpenInNew,
      tableHeight: 0,
    };
  },
  computed: {
    ...mapState(useAdminStore, {
      libraries: (state) => state.libraries,
      formErrors: (state) => state.form.errors,
      tableMaxHeight: (state) =>
        (state.libraries.length + 1) * TABLE_ROW_HEIGHT,
    }),
    ...mapGetters(useAdminStore, ["groupMap"]),
  },
  mounted() {
    this.onResize();
    window.addEventListener("resize", this.onResize);
  },
  unmounted() {
    window.removeEventListener("resize", this.onResize);
  },
  methods: {
    ...mapActions(useAdminStore, ["updateRow", "clearErrors", "librarianTask"]),
    formatDateTime: (dttm) => {
      if (!dttm) {
        return "";
      }
      return DATETIME_FORMAT.format(new Date(dttm));
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
    onResize() {
      const availableHeight = window.innerHeight - BUFFER;
      this.tableHeight =
        this.tableMaxHeight < availableHeight
          ? undefined
          : Math.max(availableHeight, MIN_TABLE_HEIGHT);
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
  color: grey;
}
</style>

<template>
  <div>
    <header class="tabHeader">
      <AdminLibraryAddDialog id="libraryAdd" />
    </header>
    <v-simple-table class="highlight-simple-table" fixed-header>
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
            <th>Delete</th>
          </tr>
        </thead>
        <tbody>
          <tr v-for="item in libraries" :key="item.id">
            <td>{{ item.path }}</td>
            <td>
              <v-checkbox
                :input-value="item.events"
                dense
                ripple
                hide-details="auto"
                :error-messages="getFormErrors(item.id, 'events')"
                @focus="clearErrors"
                @blur="item.keyHack = Date.now()"
                @change="changeCol(item.id, 'events', $event === true)"
              />
            </td>
            <td>
              <v-checkbox
                :input-value="item.poll"
                dense
                ripple
                hide-details="auto"
                :error-messages="getFormErrors(item.id, 'poll')"
                @focus="clearErrors"
                @blur="item.keyHack = Date.now()"
                @change="changeCol(item.id, 'poll', $event === true)"
              />
            </td>
            <td class="pollEveryCol">
              <TimeTextField
                :disabled="!item.poll"
                :value="item.pollEvery"
                dense
                ripple
                hide-details="auto"
                :error-messages="getFormErrors(item.id, 'poll')"
                @focus="clearErrors"
                @blur="item.keyHack = Date.now()"
                @change="changeCol(item.id, 'pollEvery', $event)"
              />
            </td>
            <td class="dateCol">
              <DateTimeColumn :dttm="item.lastPoll" />
            </td>
            <td>
              <AdminRelationPicker
                :items="vuetifyGroups"
                :value="item.groups"
                dense
                ripple
                hide-details="auto"
                :error-messages="getFormErrors(item.id, 'groups')"
                @focus="clearErrors"
                @blur="item.keyHack = Date.now()"
                @change="changeCol(item.id, 'groups', $event)"
              />
            </td>
            <td>
              <v-btn icon ripple @click="poll(item.id)"
                ><v-icon>{{ mdiDatabaseClockOutline }}</v-icon></v-btn
              >
            </td>
            <td>
              <AdminTaskConfirmDialog
                :task="{
                  icon: true,
                  text: `Force Update ${item.path}`,
                  confirm: 'This can take a long time',
                }"
                @confirmed="forcePoll(item.id)"
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
import AdminLibraryAddDialog from "@/components/admin/library-add-dialog.vue";
import AdminRelationPicker from "@/components/admin/relation-picker.vue";
import AdminTaskConfirmDialog from "@/components/admin/task-dialog.vue";
import TimeTextField from "@/components/admin/time-text-field.vue";
import { DATETIME_FORMAT } from "@/datetime";
import { useAdminStore } from "@/stores/admin";

export default {
  name: "AdminLibrariesPanel",
  components: {
    AdminDeleteRowDialog,
    AdminFailedImportsPanel,
    AdminLibraryAddDialog,
    AdminRelationPicker,
    AdminTaskConfirmDialog,
    DateTimeColumn,
    TimeTextField,
  },
  data() {
    return {
      lastUpdate: {
        pk: 0,
        field: undefined,
      },
      mdiDatabaseClockOutline,
      mdiOpenInNew,
    };
  },
  computed: {
    ...mapState(useAdminStore, {
      libraries: (state) => state.libraries,
      formErrors: (state) => state.form.errors,
    }),
    ...mapGetters(useAdminStore, ["vuetifyGroups"]),
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
</style>

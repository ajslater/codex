<template>
  <div>
    <header class="tabHeader">
      <AdminGroupAddDialog id="groupAddDialog" />
    </header>
    <v-simple-table
      fixed-header
      :height="tableHeight"
      class="highlight-simple-table"
    >
      <template #default>
        <thead>
          <tr>
            <th>Name</th>
            <th>Users</th>
            <th>Libraries</th>
            <th>Delete</th>
          </tr>
        </thead>
        <tbody>
          <tr v-for="item in groups" :key="`g:${item.pk}:${item.keyHack}`">
            <td class="nameCol">
              <v-text-field
                :value="item.name"
                dense
                round
                filled
                hide-details="auto"
                :error-messages="getFormErrors(item.pk, 'name')"
                @focus="clearErrors"
                @blur="item.keyHack = Date.now()"
                @change="changeCol(item.pk, 'name', $event)"
              />
            </td>
            <td>
              <AdminRelationPicker
                :items="vuetifyUsers"
                :value="item.userSet"
                hide-details="auto"
                :error-messages="getFormErrors(item.pk, 'userSet')"
                @focus="clearErrors"
                @blur="item.keyHack = Date.now()"
                @change="changeCol(item.pk, 'userSet', $event)"
              />
            </td>
            <td>
              <AdminRelationPicker
                :items="vuetifyLibraries"
                :value="item.librarySet"
                hide-details="auto"
                :error-messages="getFormErrors(item.pk, 'userSet')"
                @focus="clearErrors"
                @blur="item.keyHack = Date.now()"
                @change="changeCol(item.pk, 'librarySet', $event)"
              />
            </td>
            <td>
              <AdminDeleteRowDialog
                table="Group"
                :pk="item.pk"
                :name="item.name"
              />
            </td>
          </tr>
        </tbody>
      </template>
    </v-simple-table>
    <div id="groupHelp">
      <p>
        A library with no groups is accessible to every user and non-users if
        those are enabled.
      </p>
      <p>
        A library with <em>any</em> groups is accessible <em>only</em> to users
        who are in those groups.
      </p>
      <p>
        If you have libraries added and you do not see them in your browser,
        check to see if the library and your user are in the same group.
      </p>
    </div>
  </div>
</template>

<script>
import { mapActions, mapGetters, mapState } from "pinia";

import AdminDeleteRowDialog from "@/components/admin/delete-row-dialog.vue";
import AdminGroupAddDialog from "@/components/admin/group-add-dialog.vue";
import AdminRelationPicker from "@/components/admin/relation-picker.vue";
import { useAdminStore } from "@/stores/admin";

export default {
  name: "AdminGroupsPanel",
  components: {
    AdminDeleteRowDialog,
    AdminGroupAddDialog,
    AdminRelationPicker,
  },
  data() {
    return {
      lastUpdate: {
        pk: 0,
        field: undefined,
      },
    };
  },
  computed: {
    ...mapState(useAdminStore, {
      groups: (state) => state.groups,
      formErrors: (state) => state.form.errors,
    }),
    ...mapGetters(useAdminStore, ["vuetifyLibraries", "vuetifyUsers"]),
    tableHeight: () => window.innerHeight * 0.9,
  },
  methods: {
    ...mapActions(useAdminStore, ["updateRow", "clearErrors"]),
    changeCol: function (pk, field, val) {
      this.lastUpdate.pk = pk;
      this.lastUpdate.field = field;
      const data = { [field]: val };
      this.updateRow("Group", pk, data);
    },
    getFormErrors(pk, field) {
      if (pk === this.lastUpdate.pk && field === this.lastUpdate.field) {
        return this.formErrors;
      }
    },
  },
};
</script>

<style scoped lang="scss">
.nameCol {
  min-width: 10em;
}
#groupHelp {
  margin-top: 2em;
  color: lightgrey;
}
</style>

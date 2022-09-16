<template>
  <div>
    <header class="tabHeader">
      <AdminUserAddDialog id="userAdd" />
    </header>
    <v-simple-table
      fixed-header
      :height="tableHeight"
      class="highlight-simple-table"
    >
      <template #default>
        <thead>
          <tr>
            <th>Username</th>
            <th>Staff</th>
            <th>Active</th>
            <th>Groups</th>
            <th>Last Login</th>
            <th>Joined</th>
            <th>Change Password</th>
            <th>Delete</th>
          </tr>
        </thead>
        <tbody>
          <tr v-for="item in users" :key="`u:${item.pk}:${item.keyHack}`">
            <td class="usernameCol">
              <v-text-field
                :value="item.username"
                dense
                round
                filled
                hide-details="auto"
                :error-messages="getFormErrors(item.pk, 'username')"
                @focus="clearErrors"
                @blur="item.keyHack = Date.now()"
                @change="changeCol(item.pk, 'username', $event)"
              />
            </td>
            <td>
              <v-checkbox
                :input-value="item.isStaff"
                dense
                ripple
                hide-details="auto"
                :error-messages="getFormErrors(item.pk, 'isStaff')"
                @focus="clearErrors"
                @blur="item.keyHack = Date.now()"
                @change="changeCol(item.pk, 'isStaff', $event === true)"
              />
            </td>
            <td>
              <v-checkbox
                :input-value="item.isActive"
                dense
                ripple
                hide-details="auto"
                :error-messages="getFormErrors(item.pk, 'isActive')"
                @focus="clearErrors"
                @blur="item.keyHack = Date.now()"
                @change="changeCol(item.pk, 'isActive', $event === true)"
              />
            </td>
            <td class="relationCol">
              <AdminRelationPicker
                :items="vuetifyGroups"
                :value="item.groups"
                hide-details="auto"
                :error-messages="getFormErrors(item.pk, 'groupSet')"
                @focus="clearErrors"
                @blur="item.keyHack = Date.now()"
                @change="changeCol(item.pk, 'groups', $event)"
              />
            </td>
            <td class="dttmCol">
              <DateTimeColumn :dttm="item.lastLogin" />
            </td>
            <td class="dttmCol">
              <DateTimeColumn :dttm="item.dateJoined" />
            </td>
            <td>
              <AdminChangePasswordDialog
                :pk="item.pk"
                :username="item.username"
                @close="item.showPasswordChangeDialog = false"
              />
            </td>
            <td>
              <!-- TODO use user.pk -->
              <AdminDeleteRowDialog
                v-if="me.username !== item.username"
                table="User"
                :pk="item.pk"
                :name="item.username"
              />
            </td>
          </tr>
        </tbody>
      </template>
    </v-simple-table>
  </div>
</template>

<script>
import { mapActions, mapGetters, mapState } from "pinia";

import AdminChangePasswordDialog from "@/components/admin/change-password-dialog.vue";
import DateTimeColumn from "@/components/admin/datetime-column.vue";
import AdminDeleteRowDialog from "@/components/admin/delete-row-dialog.vue";
import AdminRelationPicker from "@/components/admin/relation-picker.vue";
import AdminUserAddDialog from "@/components/admin/user-add-dialog.vue";
import { useAdminStore } from "@/stores/admin";
import { useAuthStore } from "@/stores/auth";

export default {
  name: "AdminUsersPanel",
  components: {
    AdminDeleteRowDialog,
    AdminRelationPicker,
    AdminChangePasswordDialog,
    AdminUserAddDialog,
    DateTimeColumn,
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
      users: (state) => state.users,
      formErrors: (state) => state.form.errors,
    }),
    ...mapState(useAuthStore, {
      me: (state) => state.user,
    }),
    ...mapGetters(useAdminStore, ["vuetifyGroups"]),
    tableHeight: () => window.innerHeight * 0.9,
  },
  methods: {
    ...mapActions(useAdminStore, ["updateRow", "clearErrors"]),
    changeCol: function (pk, field, val) {
      this.lastUpdate.pk = pk;
      this.lastUpdate.field = field;
      const data = { [field]: val };
      this.updateRow("User", pk, data);
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
.usernameCol {
  min-width: 11em;
}
.relationCol {
  min-width: 200px;
}
.dttmCol {
  min-width: 9em;
}
</style>

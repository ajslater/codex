<template>
  <div>
    <header class="tabHeader">
      <AdminUserCreateUpdateDialog id="userAdd" />
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
            <th>Update</th>
            <th>Change Password</th>
            <th>Delete</th>
          </tr>
        </thead>
        <tbody>
          <tr v-for="item in users" :key="`u:${item.pk}:${item.keyHack}`">
            <td class="usernameCol">
              {{ item.username }}
            </td>
            <td class="buttonCol">
              <v-simple-checkbox :value="item.isStaff" dense disabled />
            </td>
            <td class="buttonCol">
              <v-simple-checkbox :value="item.isActive" dense disabled />
            </td>
            <td class="relationCol">
              <RelationChips :pks="item.groups" :map="groupMap" />
            </td>
            <td class="dttmCol">
              <DateTimeColumn :dttm="item.lastLogin" />
            </td>
            <td class="dttmCol">
              <DateTimeColumn :dttm="item.dateJoined" />
            </td>
            <td class="buttonCol">
              <AdminUserCreateUpdateDialog :update="true" :old-user="item" />
            </td>
            <td class="buttonCol">
              <AdminChangePasswordDialog
                :pk="item.pk"
                :username="item.username"
              />
            </td>
            <td class="buttonCol">
              <AdminDeleteRowDialog
                v-if="me.id !== item.pk"
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
import { mapGetters, mapState } from "pinia";

import AdminChangePasswordDialog from "@/components/admin/change-password-dialog.vue";
import DateTimeColumn from "@/components/admin/datetime-column.vue";
import AdminDeleteRowDialog from "@/components/admin/delete-row-dialog.vue";
import RelationChips from "@/components/admin/relation-chips.vue";
import AdminUserCreateUpdateDialog from "@/components/admin/user-create-update-dialog.vue";
import { useAdminStore } from "@/stores/admin";
import { useAuthStore } from "@/stores/auth";

export default {
  name: "AdminUsersPanel",
  components: {
    AdminDeleteRowDialog,
    AdminChangePasswordDialog,
    AdminUserCreateUpdateDialog,
    DateTimeColumn,
    RelationChips,
  },
  computed: {
    ...mapState(useAdminStore, {
      users: (state) => state.users,
    }),
    ...mapState(useAuthStore, {
      me: (state) => state.user,
    }),
    ...mapGetters(useAdminStore, ["groupMap"]),
    tableHeight: () => window.innerHeight * 0.7,
  },
};
</script>

<style scoped lang="scss">
.usernameCol {
  min-width: 11em;
}
.dttmCol {
  min-width: 9em;
}
.buttonCol {
  width: 24px;
}
</style>

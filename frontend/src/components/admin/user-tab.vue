<template>
  <div>
    <header class="tabHeader">
      <AdminCreateUpdateDialog
        table="User"
        :inputs="AdminUserCreateUpdateInputs"
        max-width="20em"
      />
    </header>
    <AdminTable :items="users">
      <template #thead>
        <tr>
          <th>Username</th>
          <th>Staff</th>
          <th>Active</th>
          <th>Groups</th>
          <th>Last Login</th>
          <th>Joined</th>
          <th>Edit</th>
          <th>Change Password</th>
          <th>Delete</th>
        </tr>
      </template>
      <template #tbody>
        <tr v-for="item in users" :key="`u:${item.pk}:${item.keyHack}`">
          <td class="usernameCol">
            {{ item.username }}
          </td>
          <td class="buttonCol">
            <v-checkbox
              class="tableCheckbox"
              :model-value="item.isStaff"
              density="compact"
              disabled
            />
          </td>
          <td class="buttonCol">
            <v-checkbox
              class="tableCheckbox"
              :model-value="item.isActive"
              density="compact"
              disabled
            />
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
            <AdminCreateUpdateDialog
              table="User"
              :inputs="AdminUserCreateUpdateInputs"
              :old-row="item"
              max-width="20em"
            />
          </td>
          <td class="buttonCol">
            <ChangePasswordDialog :user="item" :is-admin-mode="true" />
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
      </template>
    </AdminTable>
  </div>
</template>

<script>
import { mapActions, mapGetters, mapState } from "pinia";
import { markRaw } from "vue";

import AdminTable from "@/components/admin/admin-table.vue";
import AdminCreateUpdateDialog from "@/components/admin/create-update-dialog.vue";
import DateTimeColumn from "@/components/admin/datetime-column.vue";
import AdminDeleteRowDialog from "@/components/admin/delete-row-dialog.vue";
import RelationChips from "@/components/admin/relation-chips.vue";
import AdminUserCreateUpdateInputs from "@/components/admin/user-create-update-inputs.vue";
import ChangePasswordDialog from "@/components/change-password-dialog.vue";
import { useAdminStore } from "@/stores/admin";
import { useAuthStore } from "@/stores/auth";

export default {
  name: "AdminUsersTab",
  components: {
    AdminTable,
    AdminDeleteRowDialog,
    ChangePasswordDialog,
    AdminCreateUpdateDialog,
    DateTimeColumn,
    RelationChips,
  },
  data() {
    return {
      AdminUserCreateUpdateInputs: markRaw(AdminUserCreateUpdateInputs),
    };
  },
  computed: {
    ...mapGetters(useAdminStore, ["groupMap"]),
    ...mapState(useAdminStore, {
      users: (state) => state.users,
    }),
    ...mapState(useAuthStore, {
      me: (state) => state.user,
    }),
  },
  mounted() {
    this.loadTables(["Group", "User"]);
  },
  methods: {
    ...mapActions(useAdminStore, ["loadTables"]),
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

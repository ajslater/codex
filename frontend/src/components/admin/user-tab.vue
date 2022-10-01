<template>
  <div>
    <header class="tabHeader">
      <AdminCreateUpdateDialog
        table="User"
        :inputs="AdminUserCreateUpdateInputs"
        max-width="20em"
      />
    </header>
    <v-simple-table
      fixed-header
      :height="tableHeight"
      class="highlight-simple-table admin-table"
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
            <th>Edit</th>
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
              <AdminCreateUpdateDialog
                table="User"
                :inputs="AdminUserCreateUpdateInputs"
                :old-row="item"
                max-width="20em"
              />
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

import AdminChangePasswordDialog from "@/components/admin/admin-change-password-dialog.vue";
import AdminCreateUpdateDialog from "@/components/admin/create-update-dialog.vue";
import DateTimeColumn from "@/components/admin/datetime-column.vue";
import AdminDeleteRowDialog from "@/components/admin/delete-row-dialog.vue";
import RelationChips from "@/components/admin/relation-chips.vue";
import AdminUserCreateUpdateInputs from "@/components/admin/user-create-update-inputs.vue";
import { useAdminStore } from "@/stores/admin";
import { useAuthStore } from "@/stores/auth";

const FIXED_TOOLBARS = 96 + 16;
const ADD_HEADER = 36;
const TABLE_PADDING = 24;
const BUFFER = FIXED_TOOLBARS + ADD_HEADER + TABLE_PADDING;
const TABLE_ROW_HEIGHT = 48;
const MIN_TABLE_HEIGHT = TABLE_ROW_HEIGHT * 2;

export default {
  name: "AdminUsersPanel",
  components: {
    AdminDeleteRowDialog,
    AdminChangePasswordDialog,
    AdminCreateUpdateDialog,
    DateTimeColumn,
    RelationChips,
  },
  data() {
    return {
      tableHeight: undefined,
      AdminUserCreateUpdateInputs,
    };
  },
  computed: {
    ...mapState(useAdminStore, {
      users: (state) => state.users,
      tableMaxHeight: (state) => (state.users.length + 1) * TABLE_ROW_HEIGHT,
    }),
    ...mapState(useAuthStore, {
      me: (state) => state.user,
    }),
    ...mapGetters(useAdminStore, ["groupMap"]),
  },
  mounted() {
    window.addEventListener("resize", this.onResize);
    this.onResize();
  },
  unmounted() {
    window.removeEventListener("resize", this.onResize);
  },
  methods: {
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

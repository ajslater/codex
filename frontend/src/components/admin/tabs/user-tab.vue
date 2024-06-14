<template>
  <div>
    <header class="tabHeader">
      <AdminCreateUpdateDialog
        table="User"
        :inputs="AdminUserCreateUpdateInputs"
        max-width="20em"
      />
    </header>
    <AdminTable item-title="username" :headers="headers" :items="users">
      <template #no-data>
        <td class="adminNoData" colspan="100%">
          No Users.
          <div>
            This is an error. There should always be at least one Staff user.<br />
            You should not be able to see this page<br />
            You should restart Codex with the CODEX_RESET_ADMIN=1 variable
            set.<br />
            See the
            <a
              href="https://github.com/ajslater/codex#reset-the-admin-password"
              target="_blank"
            >
              README
            </a>
          </div>
        </td>
      </template>
      <template #[`item.isStaff`]="{ item }">
        <v-checkbox-btn :model-value="item.isStaff" disabled />
      </template>
      <template #[`item.isActive`]="{ item }">
        <v-checkbox-btn :model-value="item.isActive" disabled />
      </template>
      <template #[`item.groups`]="{ item }">
        <RelationChips
          :pks="item.groups"
          :objs="groups"
          title-key="name"
          group-type
        />
      </template>
      <template #[`item.lastActive`]="{ item }">
        <DateTimeColumn :dttm="item.lastActive" />
      </template>
      <template #[`item.lastLogin`]="{ item }">
        <DateTimeColumn :dttm="item.lastLogin" />
      </template>
      <template #[`item.dateJoined`]="{ item }">
        <DateTimeColumn :dttm="item.dateJoined" />
      </template>
      <template #[`item.actions`]="{ item }">
        <AdminCreateUpdateDialog
          table="User"
          :inputs="AdminUserCreateUpdateInputs"
          :old-row="item"
          max-width="20em"
          size="small"
          density="compact"
        />
        <ChangePasswordDialog
          :user="item"
          :is-admin-mode="true"
          size="small"
          density="compact"
        />
        <AdminDeleteRowDialog
          v-if="me.id !== item.pk"
          table="User"
          :pk="item.pk"
          :name="item.username"
          size="small"
          density="compact"
        />
      </template>
    </AdminTable>
  </div>
</template>

<script>
import { mapActions, mapState } from "pinia";
import { markRaw } from "vue";

import AdminCreateUpdateDialog from "@/components/admin/create-update-dialog/create-update-dialog.vue";
import AdminUserCreateUpdateInputs from "@/components/admin/create-update-dialog/user-create-update-inputs.vue";
import AdminTable from "@/components/admin/tabs/admin-table.vue";
import DateTimeColumn from "@/components/admin/tabs/datetime-column.vue";
import AdminDeleteRowDialog from "@/components/admin/tabs/delete-row-dialog.vue";
import RelationChips from "@/components/admin/tabs/relation-chips.vue";
import ChangePasswordDialog from "@/components/auth/change-password-dialog.vue";
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
      headers: [
        { title: "Username", key: "username", align: "start" },
        { title: "Staff", key: "isStaff" },
        { title: "Active", key: "isActive" },
        { title: "Groups", key: "groups" },
        { title: "Last Active", key: "lastActive" },
        { title: "Last Login", key: "lastLogin" },
        { title: "Joined", key: "dateJoined" },
        { title: "Actions", key: "actions", sortable: false },
      ],
    };
  },
  computed: {
    ...mapState(useAdminStore, {
      users: (state) => state.users,
      groups: (state) => state.groups,
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

<template>
  <div>
    <header class="tabHeader">
      <AdminCreateUpdateDialog
        table="User"
        :inputs="AdminUserCreateUpdateInputs"
        max-width="20em"
      />
    </header>
    <v-data-table-virtual
      fixed-headers
      item-value="pk"
      item-title="username"
      :headers="headers"
      :items="users"
      class="adminTable"
    >
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
        <v-checkbox-btn :model-value="item.raw.isStaff" disabled />
      </template>
      <template #[`item.isActive`]="{ item }">
        <v-checkbox-btn :model-value="item.raw.isActive" disabled />
      </template>
      <template #[`item.groups`]="{ item }">
        <RelationChips :pks="item.raw.groups" :map="groupMap" />
      </template>
      <template #[`item.lastActive`]="{ item }">
        <DateTimeColumn :dttm="item.raw.lastActive" />
      </template>
      <template #[`item.lastLogin`]="{ item }">
        <DateTimeColumn :dttm="item.raw.lastLogin" />
      </template>
      <template #[`item.dateJoined`]="{ item }">
        <DateTimeColumn :dttm="item.raw.dateJoined" />
      </template>
      <template #[`item.actions`]="{ item }">
        <AdminCreateUpdateDialog
          table="User"
          :inputs="AdminUserCreateUpdateInputs"
          :old-row="item.raw"
          max-width="20em"
          size="small"
          density="compact"
        />
        <ChangePasswordDialog
          :user="item.raw"
          :is-admin-mode="true"
          size="small"
          density="compact"
        />
        <AdminDeleteRowDialog
          v-if="me.id !== item.raw.pk"
          table="User"
          :pk="item.raw.pk"
          :name="item.raw.username"
          size="small"
          density="compact"
        />
      </template>
    </v-data-table-virtual>
  </div>
</template>

<script>
import { mapActions, mapGetters, mapState } from "pinia";
import { markRaw } from "vue";
import { VDataTableVirtual } from "vuetify/labs/components";

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
    AdminDeleteRowDialog,
    ChangePasswordDialog,
    AdminCreateUpdateDialog,
    DateTimeColumn,
    RelationChips,
    VDataTableVirtual,
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

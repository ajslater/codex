<template>
  <div>
    <header class="tabHeader">
      <AdminCreateUpdateDialog
        table="User"
        :inputs="AdminUserCreateUpdateInputs"
        max-width="20em"
      />
      <!--
        Anonymous-session ceiling is not stored per-user; it's the ``AA``
        admin flag. Show the current value read-only here, and point at
        the Flags tab where it's actually editable.
      -->
      <div class="anonAgeRating">
        Anonymous sessions see up to:
        <strong>{{ anonAgeRating }}</strong>
        <span class="anonAgeRatingHint">
          (set on the Flags tab as <em>Anonymous User Age Rating</em>.)
        </span>
      </div>
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
      <template #[`item.ageRatingMetron`]="{ item }">
        {{ ageRatingName(item.ageRatingMetron) }}
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
        { title: "Age Rating", key: "ageRatingMetron", align: "start" },
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
      ageRatingMetrons: (state) => state.ageRatingMetrons,
      flags: (state) => state.flags,
    }),
    ...mapState(useAuthStore, {
      me: (state) => state.user,
    }),
    /** Resolve the ``AA`` admin flag value for read-only display. */
    anonAgeRating() {
      const flag = (this.flags || []).find((f) => f.key === "AA");
      /*
       * The migration seeds ``AA`` to ``Adult``; fall back in case the
       * list hasn't loaded yet.
       */
      return (flag && flag.value) || "Adult";
    },
  },
  mounted() {
    /*
     * AgeRatingMetron populates the per-user dropdown and the column
     * name resolver; Flag gives us the ``AA`` value to display.
     */
    this.loadTables(["Group", "User", "AgeRatingMetron", "Flag"]);
  },
  methods: {
    ...mapActions(useAdminStore, ["loadTables"]),
    ageRatingName(pk) {
      if (pk == undefined) {
        return "Unrestricted";
      }
      const metron = (this.ageRatingMetrons || []).find((m) => m.pk === pk);
      return (metron && metron.name) || "Unrestricted";
    },
  },
};
</script>

<style scoped lang="scss">
.anonAgeRating {
  margin-top: 0.5em;
  color: rgb(var(--v-theme-textSecondary));
  font-size: 0.9em;
}

.anonAgeRatingHint {
  margin-left: 0.4em;
  font-size: 0.85em;
}
</style>

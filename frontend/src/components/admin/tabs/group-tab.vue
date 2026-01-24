<template>
  <div>
    <header class="tabHeader">
      <AdminCreateUpdateDialog
        table="Group"
        max-width="20em"
        :inputs="AdminGroupCreateUpdateInputs"
      />
    </header>
    <AdminTable item-title="name" :headers="headers" :items="groups">
      <template #no-data>
        <td class="adminNoData" colspan="100%">No groups</td>
      </template>
      <template #[`item.exclude`]="{ item }">
        <GroupChip group-type :item="groupType(item)" title-key="name" />
      </template>
      <template #[`item.userSet`]="{ item }">
        <RelationChips :pks="item.userSet" :objs="users" title-key="username" />
      </template>
      <template #[`item.librarySet`]="{ item }">
        <RelationChips
          :pks="item.librarySet"
          :objs="normalLibraries"
          title-key="path"
        />
      </template>
      <template #[`item.actions`]="{ item }">
        <AdminCreateUpdateDialog
          table="Group"
          :old-row="item"
          max-width="20em"
          :inputs="AdminGroupCreateUpdateInputs"
          size="small"
          density="compact"
        />
        <AdminDeleteRowDialog
          table="Group"
          :pk="item.pk"
          :name="item.name"
          size="small"
          density="compact"
        />
      </template>
    </AdminTable>
    <div id="groupHelp">
      <h3>Group Access Logic</h3>
      <p>
        A library in no groups is accessible to every user and non-users if
        those are enabled.
      </p>
      <p>
        A library with <em>any</em> Include groups is accessible
        <em>only</em> to users who are in those groups.
      </p>
      <p>
        A library with <em>any</em> Exclude groups is not accessible to Guest
        users but is acccessable to any logged in users that are not in the
        Exclude groups.
      </p>
      <p>
        If you have libraries added and you do not see them in your browser,
        check to see if the library and your user are in the same group.
      </p>
      <table id="groupTable">
        <thead>
          <tr>
            <th>Library in Group Type</th>
            <th>Guest</th>
            <th>User Out of Group</th>
            <th>User In Group</th>
          </tr>
        </thead>
        <tbody>
          <tr>
            <td>Not in a Group</td>
            <td class="see">Can See</td>
            <td class="see">Can See</td>
            <td class="see">Can See</td>
          </tr>
          <tr>
            <td>
              <GroupChip
                :item="{ name: 'Include', exclude: false }"
                title-key="name"
                group-type
              />
            </td>
            <td class="hidden">Hidden</td>
            <td class="hidden">Hidden</td>
            <td class="see">Can See</td>
          </tr>
          <tr>
            <td>
              <GroupChip
                :item="{ name: 'Exclude', exclude: true }"
                title-key="name"
                group-type
              />
            </td>
            <td class="hidden">Hidden</td>
            <td class="see">Can See</td>
            <td class="hidden">Hidden</td>
          </tr>
        </tbody>
      </table>
    </div>
  </div>
</template>

<script>
import { mapActions, mapState } from "pinia";
import { markRaw } from "vue";

import AdminCreateUpdateDialog from "@/components/admin/create-update-dialog/create-update-dialog.vue";
import AdminGroupCreateUpdateInputs from "@/components/admin/create-update-dialog/group-create-update-inputs.vue";
import GroupChip from "@/components/admin/group-chip.vue";
import AdminTable from "@/components/admin/tabs/admin-table.vue";
import AdminDeleteRowDialog from "@/components/admin/tabs/delete-row-dialog.vue";
import RelationChips from "@/components/admin/tabs/relation-chips.vue";
import { useAdminStore } from "@/stores/admin";

const GROUP_HELP_HEIGHT = 180;

export default {
  name: "AdminGroupsTab",
  components: {
    AdminTable,
    AdminDeleteRowDialog,
    AdminCreateUpdateDialog,
    RelationChips,
    GroupChip,
  },
  data() {
    return {
      lastUpdate: {
        pk: 0,
        field: undefined,
      },
      AdminGroupCreateUpdateInputs: markRaw(AdminGroupCreateUpdateInputs),
      GROUP_HELP_HEIGHT,
      headers: [
        { title: "Name", key: "name", align: "start" },
        { title: "Type", key: "exclude", align: "start" },
        { title: "Users", key: "userSet" },
        { title: "Libraries", key: "librarySet" },
        { title: "Actions", key: "actions", sortable: false },
      ],
    };
  },
  computed: {
    ...mapState(useAdminStore, ["normalLibraries"]),
    ...mapState(useAdminStore, {
      groups: (state) => state.groups,
      users: (state) => state.users,
    }),
  },
  mounted() {
    this.loadTables(["User", "Library", "Group"]);
  },
  methods: {
    ...mapActions(useAdminStore, ["loadTables"]),
    groupType(item) {
      const exclude = item.exclude;
      const name = exclude ? "Exclude " : "Include";
      return { name, exclude };
    },
  },
};
</script>

<style scoped lang="scss">
#groupHelp {
  margin-top: 2em;
  margin-bottom: 2em;
  color: rgb(var(--v-theme-textSecondary));
}

#groupTable {
  border: solid thin;
  margin-top: 1em;
}

#groupTable th,
#groupTable td {
  padding: 0.25em;
}

.see {
  background-color: rgb(var(--v-theme-includeGroup));
}

.hidden {
  background-color: rgb(var(--v-theme-excludeGroup));
}
</style>

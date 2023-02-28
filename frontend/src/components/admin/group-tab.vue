<template>
  <div>
    <header class="tabHeader">
      <AdminCreateUpdateDialog
        table="Group"
        max-width="20em"
        :inputs="AdminGroupCreateUpdateInputs"
      />
    </header>
    <AdminTable :items="groups" :extra-height="GROUP_HELP_HEIGHT">
      <template #thead>
        <tr>
          <th>Name</th>
          <th>Users</th>
          <th>Libraries</th>
          <th>Edit</th>
          <th>Delete</th>
        </tr>
      </template>
      <template #tbody>
        <tr v-for="item in groups" :key="`g:${item.pk}:${item.keyHack}`">
          <td class="nameCol">
            {{ item.name }}
          </td>
          <td>
            <RelationChips :pks="item.userSet" :map="userMap" />
          </td>
          <td>
            <RelationChips :pks="item.librarySet" :map="libraryMap" />
          </td>
          <td>
            <AdminCreateUpdateDialog
              table="Group"
              :old-row="item"
              max-width="20em"
              :inputs="AdminGroupCreateUpdateInputs"
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
      </template>
    </AdminTable>
    <div id="groupHelp">
      <h3>Group Logic</h3>
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
import { markRaw } from "vue";

import AdminTable from "@/components/admin/admin-table.vue";
import AdminCreateUpdateDialog from "@/components/admin/create-update-dialog.vue";
import AdminDeleteRowDialog from "@/components/admin/delete-row-dialog.vue";
import AdminGroupCreateUpdateInputs from "@/components/admin/group-create-update-inputs.vue";
import RelationChips from "@/components/admin/relation-chips.vue";
import { useAdminStore } from "@/stores/admin";

const GROUP_HELP_HEIGHT = 180;

export default {
  name: "AdminGroupsTab",
  components: {
    AdminTable,
    AdminDeleteRowDialog,
    AdminCreateUpdateDialog,
    RelationChips,
  },
  data() {
    return {
      lastUpdate: {
        pk: 0,
        field: undefined,
      },
      AdminGroupCreateUpdateInputs: markRaw(AdminGroupCreateUpdateInputs),
      GROUP_HELP_HEIGHT,
    };
  },
  computed: {
    ...mapState(useAdminStore, {
      groups: (state) => state.groups,
    }),
    ...mapGetters(useAdminStore, ["libraryMap", "userMap"]),
  },
  mounted() {
    this.loadTables(["User", "Library", "Group"]);
  },
  methods: {
    ...mapActions(useAdminStore, ["loadTables"]),
  },
};
</script>

<style scoped lang="scss">
.nameCol {
  min-width: 10em;
}
#groupHelp {
  margin-top: 2em;
  color: rgb(var(--v-theme-textSecondary));
}
</style>

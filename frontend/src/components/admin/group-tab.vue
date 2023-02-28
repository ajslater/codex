<template>
  <div>
    <header class="tabHeader">
      <AdminCreateUpdateDialog
        table="Group"
        max-width="20em"
        :inputs="AdminGroupCreateUpdateInputs"
      />
    </header>
    <v-table
      fixed-header
      :height="tableHeight"
      class="highlight-table admin-table"
    >
      <template #default>
        <thead>
          <tr>
            <th>Name</th>
            <th>Users</th>
            <th>Libraries</th>
            <th>Edit</th>
            <th>Delete</th>
          </tr>
        </thead>
        <tbody :style="tbodyStyle">
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
        </tbody>
      </template>
    </v-table>
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

import AdminCreateUpdateDialog from "@/components/admin/create-update-dialog.vue";
import AdminDeleteRowDialog from "@/components/admin/delete-row-dialog.vue";
import AdminGroupCreateUpdateInputs from "@/components/admin/group-create-update-inputs.vue";
import RelationChips from "@/components/admin/relation-chips.vue";
import { useAdminStore } from "@/stores/admin";

const FIXED_TOOLBARS = 96 + 16;
const ADD_HEADER = 36;
const GROUP_HELP = 180;
const TABLE_PADDING = 24;
const BUFFER = FIXED_TOOLBARS + ADD_HEADER + GROUP_HELP + TABLE_PADDING;
const TABLE_ROW_HEIGHT = 48;
const MIN_TABLE_HEIGHT = TABLE_ROW_HEIGHT * 2;
const ROW_HEIGHT = 84;

export default {
  name: "AdminGroupsTab",
  components: {
    AdminDeleteRowDialog,
    AdminCreateUpdateDialog,
    RelationChips,
  },
  props: {
    innerHeight: {
      type: Number,
      required: true,
    },
  },
  data() {
    return {
      lastUpdate: {
        pk: 0,
        field: undefined,
      },
      AdminGroupCreateUpdateInputs: markRaw(AdminGroupCreateUpdateInputs),
    };
  },
  computed: {
    ...mapState(useAdminStore, {
      groups: (state) => state.groups,
      tableMaxHeight: (state) => (state.groups.length + 1) * TABLE_ROW_HEIGHT,
    }),
    ...mapGetters(useAdminStore, ["libraryMap", "userMap"]),
    tableHeight() {
      const availableHeight = this.innerHeight - BUFFER;
      return this.tableMaxHeight < availableHeight
        ? undefined
        : Math.max(availableHeight, MIN_TABLE_HEIGHT);
    },
    tbodyStyle() {
      return this.groups
        ? { height: ROW_HEIGHT * this.groups.length + "px" }
        : {};
    },
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

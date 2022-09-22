<template>
  <div>
    <header class="tabHeader">
      <AdminGroupCreateUpdateDialog />
    </header>
    <v-simple-table
      fixed-header
      :height="tableHeight"
      class="highlight-simple-table"
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
        <tbody>
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
              <AdminGroupCreateUpdateDialog :update="true" :old-group="item" />
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
    </v-simple-table>
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
import { mapGetters, mapState } from "pinia";

import AdminDeleteRowDialog from "@/components/admin/delete-row-dialog.vue";
import AdminGroupCreateUpdateDialog from "@/components/admin/group-create-update-dialog.vue";
import RelationChips from "@/components/admin/relation-chips.vue";
import { useAdminStore } from "@/stores/admin";

const FIXED_TOOLBARS = 96 + 16;
const ADD_HEADER = 36;
const GROUP_HELP = 180;
const BUFFER = FIXED_TOOLBARS + ADD_HEADER + GROUP_HELP;
const TABLE_ROW_HEIGHT = 48;
const MIN_TABLE_HEIGHT = TABLE_ROW_HEIGHT * 2;

export default {
  name: "AdminGroupsPanel",
  components: {
    AdminDeleteRowDialog,
    AdminGroupCreateUpdateDialog,
    RelationChips,
  },
  data() {
    return {
      lastUpdate: {
        pk: 0,
        field: undefined,
      },
      tableHeight: 0,
    };
  },
  computed: {
    ...mapState(useAdminStore, {
      groups: (state) => state.groups,
      tableMaxHeight: (state) => (state.groups.length + 1) * TABLE_ROW_HEIGHT,
    }),
    ...mapGetters(useAdminStore, ["libraryMap", "userMap"]),
  },
  mounted() {
    this.onResize();
    window.addEventListener("resize", this.onResize);
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
.nameCol {
  min-width: 10em;
}
#groupHelp {
  margin-top: 2em;
  color: darkgrey;
}
</style>

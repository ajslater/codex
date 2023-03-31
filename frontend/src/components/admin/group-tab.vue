<template>
  <div>
    <header class="tabHeader">
      <AdminCreateUpdateDialog
        table="Group"
        max-width="20em"
        :inputs="AdminGroupCreateUpdateInputs"
      />
    </header>
    <v-data-table-virtual
      class="adminTable"
      fixed-headers
      item-value="pk"
      item-title="name"
      :headers="headers"
      :items="groups"
    >
      <template #no-data>
        <td class="adminNoData" colspan="100%">No groups</td>
      </template>
      <template #[`item.userSet`]="{ item }">
        <RelationChips :pks="item.raw.userSet" :map="userMap" />
      </template>
      <template #[`item.librarySet`]="{ item }">
        <RelationChips :pks="item.raw.librarySet" :map="libraryMap" />
      </template>
      <template #[`item.actions`]="{ item }">
        <AdminCreateUpdateDialog
          table="Group"
          :old-row="item.raw"
          max-width="20em"
          :inputs="AdminGroupCreateUpdateInputs"
          size="small"
          density="compact"
        />
        <AdminDeleteRowDialog
          table="Group"
          :pk="item.raw.pk"
          :name="item.raw.name"
          size="small"
          density="compact"
        />
      </template>
    </v-data-table-virtual>
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
import { VDataTableVirtual } from "vuetify/labs/components";

import AdminCreateUpdateDialog from "@/components/admin/create-update-dialog.vue";
import AdminDeleteRowDialog from "@/components/admin/delete-row-dialog.vue";
import AdminGroupCreateUpdateInputs from "@/components/admin/group-create-update-inputs.vue";
import RelationChips from "@/components/admin/relation-chips.vue";
import { useAdminStore } from "@/stores/admin";

const GROUP_HELP_HEIGHT = 180;

export default {
  name: "AdminGroupsTab",
  components: {
    AdminDeleteRowDialog,
    AdminCreateUpdateDialog,
    RelationChips,
    VDataTableVirtual,
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
        { title: "Users", key: "userSet" },
        { title: "Libraries", key: "librarySet" },
        { title: "Actions", key: "actions", sortable: false },
      ],
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
#groupHelp {
  margin-top: 2em;
  color: rgb(var(--v-theme-textSecondary));
}
</style>

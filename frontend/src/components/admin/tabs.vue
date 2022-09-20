<template>
  <div id="tabs">
    <v-tabs v-model="tab" centered grow show-arrows>
      <v-tab v-for="name of Object.keys(panels)" :key="name">
        {{ name }}
      </v-tab>
    </v-tabs>
    <v-tabs-items id="tabItems" v-model="tab">
      <v-tab-item
        v-for="name of Object.keys(panels)"
        :key="name"
        class="tabItem"
      >
        <component :is="panels[name]" />
      </v-tab-item>
    </v-tabs-items>
    <div v-if="!librariesExist" id="noLibraries">
      Codex has no libraries. Select the Libraries tab and add a comic library.
    </div>
  </div>
</template>

<script>
import { mapActions, mapGetters } from "pinia";

import AdminFlagsPanel from "@/components/admin/flag-tab.vue";
import AdminGroupPanel from "@/components/admin/group-tab.vue";
import AdminLibrarysPanel from "@/components/admin/library-tab.vue";
import AdminTasksPanel from "@/components/admin/task-tab.vue";
import AdminUsersPanel from "@/components/admin/user-tab.vue";
import { useAdminStore } from "@/stores/admin";

const LIBRARY_TAB_INDEX = 2;

export default {
  name: "AdminTabs",
  components: {
    AdminUsersPanel,
    AdminGroupPanel,
    AdminLibrarysPanel,
    AdminFlagsPanel,
    AdminTasksPanel,
  },
  data() {
    return {
      tab: undefined,
      panels: {
        Users: AdminUsersPanel,
        Groups: AdminGroupPanel,
        Libraries: AdminLibrarysPanel,
        Flags: AdminFlagsPanel,
        Tasks: AdminTasksPanel,
      },
    };
  },
  computed: {
    ...mapGetters(useAdminStore, ["librariesExist"]),
  },
  watch: {
    tab: function (to) {
      const tabName = Object.keys(this.panels)[to];

      switch (tabName) {
        case "Users":
          this.loadTables(["Group", "User"]);
          break;
        case "Flags":
          this.loadTable("Flag");
          break;
        case "Groups":
          this.loadTables(["User", "Library", "Group"]);
          break;
        case "Libraries":
          this.loadTables(["Group", "Library", "FailedImport"]);
          break;
      }
    },
  },
  created() {
    this.tab = LIBRARY_TAB_INDEX;
  },
  methods: {
    ...mapActions(useAdminStore, ["loadTable"]),
    loadTables(tables) {
      for (const table of tables) {
        this.loadTable(table);
      }
    },
  },
};
</script>

<style scoped lang="scss">
$task-width: 256px;
#tabs {
  height: 100%;
}
#tabItems {
  height: 100%;
  padding-top: 15px;
}
$tabItemMargin: 64px;
.tabItem {
  margin-left: $tabItemMargin;
  margin-right: $tabItemMargin;
}
#noLibraries {
  text-align: center;
  padding: 1em;
}
</style>
<!-- eslint-disable-next-line vue-scoped-css/enforce-style-type -->
<style lang="scss">
#tabs .tabHeader {
  padding: 10px;
}

#tabItems .highlight-simple-table tr:nth-child(odd) {
  background-color: #121212;
}
/* dialogs live outside of most structure */
.addCancelButton {
  float: right !important;
}
</style>

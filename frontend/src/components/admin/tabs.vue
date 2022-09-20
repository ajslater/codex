<template>
  <div id="tabContainer">
    <v-tabs v-model="tab" centered grow show-arrows id="tabs">
      <v-tab v-for="name of Object.keys(tabs)" :key="name">
        {{ name }}
      </v-tab>
    </v-tabs>
    <v-tabs-items id="tabItems" v-model="tab" touchless>
      <v-tab-item
        v-for="[name, attrs] of Object.entries(tabs)"
        :key="name"
        class="tabItem"
      >
        <div class="tabItemContainer">
          <component :is="attrs.panel" />
        </div>
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
      tab: LIBRARY_TAB_INDEX,
      tabs: {
        Users: { panel: AdminUsersPanel, tables: ["Group", "User"] },
        Groups: {
          panel: AdminGroupPanel,
          tables: ["User", "Library", "Group"],
        },
        Libraries: {
          panel: AdminLibrarysPanel,
          tables: ["Group", "Library", "FailedImport"],
        },
        Flags: { panel: AdminFlagsPanel, tables: ["Flag"] },
        Tasks: { panel: AdminTasksPanel, tables: [] },
      },
    };
  },
  computed: {
    ...mapGetters(useAdminStore, ["librariesExist"]),
  },
  watch: {
    tab: function () {
      this.loadTab();
    },
  },
  created() {
    this.loadTab();
  },
  methods: {
    ...mapActions(useAdminStore, ["loadTable"]),
    loadTables(tables) {
      for (const table of tables) {
        this.loadTable(table);
      }
    },
    loadTab() {
      const tables = Object.values(this.tabs)[this.tab].tables;
      this.loadTables(tables);
    },
  },
};
</script>

<style scoped lang="scss">
#tabs {
  position: fixed;
  top: 48px;
  z-index: 10;
}

$task-width: 256px;
#tabItems {
  margin-top: 96px;
  padding-top: 15px;
  width: 100%;
}
.tabItem {
  padding-left: 10px;
  padding-right: 10px;
}
.tabItemContainer {
  max-width: 1024px;
  margin-left: auto;
  margin-right: auto;
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

/* Turn off hover highlighting on v-simple-table */
#tabItems .v-data-table > .v-data-table__wrapper > table > tbody > tr:hover {
  background-color: inherit !important;
}

#tabItems .highlight-simple-table tr:nth-child(odd),
#tabItems
  .highlight-simple-table
  > .v-data-table__wrapper
  > table
  > tbody
  > tr:nth-child(odd):hover {
  background-color: #121212 !important;
}
</style>

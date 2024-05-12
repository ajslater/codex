<template>
  <div id="tabContainer">
    <v-tabs
      :class="{ rightMargin: !$vuetify.display.mdAndDown }"
      class="adminTabs"
      grow
      show-arrows
    >
      <v-tab
        v-for="tab in tabs"
        :key="tab"
        v-model="activeTab"
        :to="tab.toLowerCase()"
      >
        {{ tab }}
      </v-tab>
    </v-tabs>
    <v-window id="tabItems" v-model="activeTab" :touch="false">
      <router-view v-for="tab in tabs" :key="tab" v-slot="{ Component }">
        <v-window-item :value="tab" class="tabItemContainer">
          <component :is="Component" />
        </v-window-item>
      </router-view>
    </v-window>
    <div v-if="!librariesExist" id="noLibraries">
      Codex has no libraries. Select the Libraries tab and add a comic library.
    </div>
  </div>
</template>

<script>
import { mapActions, mapGetters } from "pinia";
import titleize from "titleize";

import { useAdminStore } from "@/stores/admin";
export default {
  name: "AdminTabs",
  data() {
    return {
      activeTab: "Libraries",
      tabs: ["Users", "Groups", "Libraries", "Flags", "Tasks", "Stats"],
    };
  },
  computed: {
    ...mapGetters(useAdminStore, ["librariesExist"]),
  },
  watch: {
    $route(to) {
      const parts = to.path.split("/");
      const lastPart = parts.at(-1);
      this.activeTab = titleize(lastPart);
    },
  },
  mounted() {
    if (!this.librariesExist) {
      this.loadTables(["Library"]);
    }
  },
  methods: {
    ...mapActions(useAdminStore, ["loadTables"]),
  },
};
</script>

<style scoped lang="scss">
#tabContainer {
  padding-top: 48px;
}
.adminTabs{
  position: fixed;
  width: 100%;
  z-index: 10;
  background-color: rgb(var(--v-theme-surface));
}
:deep(.tabHeader) {
  padding: 10px;
}
$task-width: 256px;
#tabItems {
  margin-top: 54px;

}
.tabItemContainer {
  width: 100vw;
  padding-left: max(10px, env(safe-area-inset-left));
  padding-right: max(10px, env(safe-area-inset-right));
  padding-bottom: max(10px, env(safe-area-inset-bottom));

}
#noLibraries {
  text-align: center;
  padding: 1em;
}
.rightMargin {
  width: calc(100% - 256px) !important;
}
</style>

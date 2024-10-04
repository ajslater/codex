<template>
  <div id="tabContainer">
    <v-tabs
      class="adminTabs"
      grow
      show-arrows
      :class="{ drawerMargin: !mdAndDown }"
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
    <div v-if="!doNormalComicLibrariesExist" id="noLibraries">
      Codex has no libraries. Select the Libraries tab and add a comic library.
    </div>
  </div>
</template>

<script>
import { capitalCase } from "change-case-all";
import { mapActions, mapGetters, mapState } from "pinia";

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
    ...mapGetters(useAdminStore, ["doNormalComicLibrariesExist"]),
    ...mapState(useAdminStore, {
      librariesLoaded: (state) => Boolean(state.libraries),
    }),
    mdAndDown() {
      return this.$vuetify.display.mdAndDown;
    },
  },
  watch: {
    $route(to) {
      const parts = to.path.split("/");
      const lastPart = parts.at(-1);
      this.activeTab = capitalCase(lastPart);
    },
  },
  mounted() {
    if (!this.librariesLoaded) {
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

.adminTabs {
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
  width: 100%;
  padding-left: max(10px, env(safe-area-inset-left));
  padding-right: max(10px, env(safe-area-inset-right));
  padding-bottom: max(10px, env(safe-area-inset-bottom));

}

#noLibraries {
  text-align: center;
  padding: 1em;
}

.drawerMargin {
  width: calc(100% - 256px) !important;
}
</style>

<template>
  <div id="tabContainer">
    <v-tabs
      id="tabs"
      :class="{ rightMargin: !$vuetify.display.mdAndDown }"
      centered
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
      <router-view
        v-for="tab in tabs"
        :key="tab"
        v-slot="{ Component }"
        :inner-height="innerHeight"
      >
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

import { useAdminStore } from "@/stores/admin";

export default {
  name: "AdminTabs",
  data() {
    return {
      activeTab: "Libraries",
      tabs: ["Users", "Groups", "Libraries", "Flags", "Tasks", "Stats"],
      innerHeight: window.innerHeight,
    };
  },
  computed: {
    ...mapGetters(useAdminStore, ["librariesExist"]),
  },
  watch: {
    $route(to) {
      const parts = to.path.split("/");
      const lastPart = parts.at(-1);
      this.activeTab = lastPart[0].toUpperCase() + lastPart.slice(1);
    },
  },
  mounted() {
    window.addEventListener("resize", this.onResize);
    if (!this.librariesExist) {
      this.loadTables(["Library"]);
    }
  },
  unmounted() {
    window.removeEventListener("resize", this.onResize);
  },
  methods: {
    ...mapActions(useAdminStore, ["loadTables"]),
    onResize() {
      this.innerHeight = window.innerHeight;
    },
  },
};
</script>

<style scoped lang="scss">
#tabs {
  position: fixed;
  width: 100%;
  top: 48px;
  z-index: 10;
  background-color: rgb(var(--v-theme-surface));
}
:deep(.tabHeader) {
  padding: 10px;
}

$task-width: 256px;
#tabItems {
  margin-top: 96px;
  padding-top: 15px;
  padding-left: env(safe-area-inset-left);
  padding-right: env(safe-area-inset-right);
}
.tabItemContainer {
  max-width: 1200px;
  margin-left: auto;
  margin-right: auto;
  padding-left: 10px;
  padding-right: 10px;
}
:deep(.admin-table) {
  max-width: 100vw !important;
  margin-bottom: 24px;
}
:deep(.tableCheckbox) {
  height: 40px;
}
#noLibraries {
  text-align: center;
  padding: 1em;
}
.rightMargin {
  width: calc(100% - 256px) !important;
}
</style>

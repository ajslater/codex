<template>
  <v-window v-model="activeTab" :class="classes" :touch="false">
    <router-view v-for="tab in TABS" :key="tab" v-slot="{ Component }">
      <v-window-item :value="tab" class="tabItemContainer">
        <component :is="Component" />
      </v-window-item>
    </router-view>
  </v-window>
  <div v-if="!doNormalComicLibrariesExist" id="noLibraries">
    Codex has no libraries. Select the Libraries tab and add a comic library.
  </div>
</template>

<script>
import { mapActions, mapState } from "pinia";

import { TABS, useAdminStore } from "@/stores/admin";
import { useAuthStore } from "@/stores/auth";
export default {
  name: "AdminTabs",
  data() {
    return {
      TABS,
    };
  },
  computed: {
    ...mapState(useAdminStore, ["doNormalComicLibrariesExist"]),
    ...mapState(useAuthStore, ["isBanner"]),
    ...mapState(useAdminStore, {
      librariesLoaded: (state) => Boolean(state.libraries),
      activeTab: (state) => state.activeTab,
    }),
    classes() {
      let marginClass = "tabItems";
      if (this.isBanner) {
        marginClass += "Banner";
      }
      return { [marginClass]: true };
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
$task-width: 256px;
$header-top: 92px;
$header-top-margin: calc($header-top + 24px);

.tabItems {
  margin-top: $header-top-margin;
}

.tabItemsBanner {
  margin-top: calc(20px + $header-top-margin);
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

:deep(.tabHeader) {
  // In each tab not here.
  margin-bottom: 20px;
}
</style>

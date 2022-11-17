<template>
  <div id="tabContainer">
    <v-tabs
      id="tabs"
      :class="{ rightSpace: rightSpace }"
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
    <v-window id="tabItems" v-model="activeTab" touchless>
      <v-window-item
        v-for="tab in tabs"
        :key="tab"
        :value="tab"
        class="tabItemContainer"
      >
        <router-view v-if="tab === activeTab" :inner-height="innerHeight" />
      </v-window-item>
    </v-window>
    <div v-if="!librariesExist" id="noLibraries">
      Codex has no libraries. Select the Libraries tab and add a comic library.
    </div>
  </div>
</template>

<script>
import { mapGetters } from "pinia";

import { useAdminStore } from "@/stores/admin";

export default {
  name: "AdminTabs",
  data() {
    return {
      activeTab: "Libraries",
      tabs: ["Users", "Groups", "Libraries", "Flags", "Tasks"],
      innerHeight: window.innerHeight,
    };
  },
  computed: {
    ...mapGetters(useAdminStore, ["librariesExist"]),
    rightSpace() {
      return !this.$vuetify.display.mobile;
    },
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
  },
  unmounted() {
    window.removeEventListener("resize", this.onResize);
  },
  methods: {
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
}

$task-width: 256px;
#tabItems {
  margin-top: 96px;
  padding-top: 15px;
  padding-left: env(safe-area-inset-left);
  padding-right: env(safe-area-inset-right);
}
.tabItemContainer {
  max-width: 1024px;
  margin-left: auto;
  margin-right: auto;
  padding-left: 10px;
  padding-right: 10px;
}
#noLibraries {
  text-align: center;
  padding: 1em;
}
.rightSpace {
  width: calc(100% - 256px) !important;
}
</style>
<!-- eslint-disable-next-line vue-scoped-css/enforce-style-type -->
<style lang="scss">
#tabs .tabHeader {
  padding: 10px;
}

/* Turn off hover highlighting on v-table */
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

.admin-table {
  padding-bottom: 24px;
}
</style>

<template>
  <div v-if="stats" id="stats">
    <StatsTable title="Platform" :items="platformTable" />
    <!--
      API Key + regenerate button moved to the Settings tab. The
      stats payload still exposes ``stats.config.apiKey`` but the
      Config table here drops it from the rendered keys.
    -->
    <StatsTable title="Config" :items="configTable" />
    <StatsTable title="File Types" :items="fileTypesTable" />
    <StatsTable title="User Settings" :items="userSettingsTable" />
    <StatsTable title="Browser Groups" :items="browserGroupsTable" />
    <StatsTable title="Tags" :items="metadataTable" />
  </div>
</template>

<script>
import { mapActions, mapState } from "pinia";
import { capitalCase, snakeCase } from "text-case";

import StatsTable from "@/components/admin/tabs/stats-table.vue";
import { useAdminStore } from "@/stores/admin";
import { useCommonStore } from "@/stores/common";

import { ORDER_BY, TOP_GROUP } from "@/choices/browser-map.json";
import { FIT_TO, READING_DIRECTION } from "@/choices/reader-map.json";

const LOOKUPS = Object.freeze({
  topGroup: TOP_GROUP,
  orderBy: ORDER_BY,
  fitTo: FIT_TO,
  readingDirection: READING_DIRECTION,
});
const CONFIG_LABELS = Object.freeze({
  authGroupCount: "Authorization Groups",
  libraryCount: "Libraries",
  userAnonymousCount: "Anonymous Users",
  userRegisteredCount: "Registered Users",
});
const INDENT_KEYS = Object.freeze(
  new Set([
    "creditPersonsCount",
    "creditRolesCount",
    "identifierSourcesCount",
    "storyArcNumbersCount",
  ]),
);

export default {
  name: "AdminStatsTab",
  components: {
    StatsTable,
  },
  data() {
    return {
      showTooltip: { show: false },
    };
  },
  computed: {
    ...mapState(useCommonStore, {}),
    ...mapState(useAdminStore, {
      stats: (state) => state.stats,
    }),
    platformTable() {
      const table = {};
      for (const [key, value] of Object.entries(this.stats?.platform)) {
        const label = this.keyToLabel(key);
        const labelValue =
          key === "system" ? `${value.name} ${value.release}` : value;
        Reflect.set(table, label, labelValue);
      }
      return table;
    },
    configTable() {
      const table = {};
      for (const [key, value] of Object.entries(this.stats?.config)) {
        if (key == "apiKey") {
          continue;
        }
        const label = Reflect.get(CONFIG_LABELS, key);
        Reflect.set(table, label, value);
      }
      return table;
    },
    userSettingsTable() {
      const table = {};
      for (const [key, countObj] of Object.entries(this.stats?.sessions)) {
        const countTable = {};
        const lookup = Reflect.get(LOOKUPS, key);
        for (const [typeKey, count] of Object.entries(countObj)) {
          const typeLabel = lookup
            ? Reflect.get(lookup, snakeCase(typeKey))
            : typeKey;
          Reflect.set(countTable, typeLabel, count);
        }
        const label = this.keyToLabel(key);
        Reflect.set(table, label, countTable);
      }
      return table;
    },
    browserGroupsTable() {
      const table = {};
      for (const [key, value] of Object.entries(this.stats?.groups)) {
        let label = this.keyToLabel(key);
        if (label !== "Series") {
          label += "s";
        }
        Reflect.set(table, label, value);
      }
      return table;
    },
    fileTypesTable() {
      const table = {};
      for (const [key, value] of Object.entries(this.stats?.fileTypes)) {
        const label =
          key === "unknown"
            ? capitalCase(key)
            : this.keyToLabel(key).toUpperCase();
        Reflect.set(table, label, value);
      }
      return table;
    },
    metadataTable() {
      const table = {};
      for (const [key, value] of Object.entries(this.stats?.metadata)) {
        let label =
          key === "countryCount" ? "Countries" : this.keyToLabel(key) + "s";
        if (INDENT_KEYS.has(key)) {
          label = label.replace(/^\w+ /, "+");
        }
        Reflect.set(table, label, value);
      }
      return table;
    },
  },
  created() {
    this.loadStats();
  },
  methods: {
    ...mapActions(useAdminStore, ["loadStats"]),
    keyToLabel(key) {
      key = key.replace(/Count$/, "");
      return capitalCase(key);
    },
  },
};
</script>

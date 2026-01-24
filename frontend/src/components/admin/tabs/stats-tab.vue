<template>
  <div v-if="stats" id="stats">
    <StatsTable title="Platform" :items="platformTable" />
    <StatsTable title="Config" :items="configTable">
      <tbody>
        <ClipBoard
          class="apiKey"
          tooltip="Copy API Key"
          title="API Key"
          :text="stats.config.apiKey"
        />
        <tr id="schemaDoc">
          <td colspan="2">
            <div>
              The only endpoint accessible by API Key is
              <!-- eslint-disable-next-line sonarjs/no-vue-bypass-sanitization -->
              <a :href="schemaHref" target="_blank">/admin/stats</a>
            </div>
            <ConfirmDialog
              button-text="Regenerate API Key"
              title-text="Regenerate"
              text="API Key"
              confirm-text="Regenerate"
              @confirm="regenAPIKey"
            />
          </td>
        </tr>
      </tbody>
    </StatsTable>
    <StatsTable title="User Settings" :items="userSettingsTable" />
    <StatsTable title="Browser Groups" :items="browserGroupsTable" />
    <StatsTable title="File Types" :items="fileTypesTable" />
    <StatsTable title="Metadata" :items="metadataTable" />
  </div>
</template>

<script>
import { mapActions, mapState } from "pinia";
import { capitalCase, snakeCase } from "text-case";

import StatsTable from "@/components/admin/tabs/stats-table.vue";
import ClipBoard from "@/components/clipboard.vue";
import ConfirmDialog from "@/components/confirm-dialog.vue";
import { useAdminStore } from "@/stores/admin";
import { useCommonStore } from "@/stores/common";

const API_TOOLTIP = "Copy API Key to clipboard";

import {
  orderBy as ORDER_BY,
  topGroup as TOP_GROUP,
} from "@/choices/browser-map.json";
import {
  fitTo as FIT_TO,
  readingDirection as READING_DIRECTION,
} from "@/choices/reader-map.json";

const LOOKUPS = {
  topGroup: TOP_GROUP,
  orderBy: ORDER_BY,
  fitTo: FIT_TO,
  readingDirection: READING_DIRECTION,
};
const CONFIG_LABELS = {
  authGroupCount: "Authorization Groups",
  libraryCount: "Libraries",
  userAnonymousCount: "Anonymous Users",
  userRegisteredCount: "Registered Users",
};
Object.freeze(CONFIG_LABELS);
Object.freeze(LOOKUPS);
const INDENT_KEYS = new Set([
  "creditPersonsCount",
  "creditRolesCount",
  "identifierSourcesCount",
  "storyArcNumbersCount",
]);
Object.freeze(INDENT_KEYS);

export default {
  name: "AdminTasksTab",
  components: {
    ClipBoard,
    ConfirmDialog,
    StatsTable,
  },
  data() {
    return {
      showTooltip: { show: false },
      schemaHref:
        globalThis.CODEX.API_V3_PATH + "#/api/api_v3_admin_stats_retrieve",
    };
  },
  computed: {
    ...mapState(useCommonStore, {}),
    ...mapState(useAdminStore, {
      stats: (state) => state.stats,
    }),
    apiTooltip() {
      return API_TOOLTIP ? this.clipBoardEnabled : undefined;
    },
    platformTable() {
      const table = {};
      for (const [key, value] of Object.entries(this.stats?.platform)) {
        const label = this.keyToLabel(key);
        const labelValue =
          key === "system" ? `${value.name} ${value.release}` : value;
        table[label] = labelValue;
      }
      return table;
    },
    configTable() {
      const table = {};
      for (const [key, value] of Object.entries(this.stats?.config)) {
        if (key == "apiKey") {
          continue;
        }
        const label = CONFIG_LABELS[key];
        table[label] = value;
      }
      return table;
    },
    userSettingsTable() {
      const table = {};
      for (const [key, countObj] of Object.entries(this.stats?.sessions)) {
        const countTable = {};
        const lookup = LOOKUPS[key];
        for (const [typeKey, count] of Object.entries(countObj)) {
          let typeLabel;
          typeLabel = lookup ? lookup[snakeCase(typeKey)] : typeKey;
          countTable[typeLabel] = count;
        }
        const label = this.keyToLabel(key);
        table[label] = countTable;
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
        table[label] = value;
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
        table[label] = value;
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
        table[label] = value;
      }
      return table;
    },
  },
  created() {
    this.loadStats();
  },
  methods: {
    ...mapActions(useAdminStore, ["loadStats", "updateAPIKey"]),
    regenAPIKey() {
      this.updateAPIKey().then(this.loadStats).catch(console.warn);
    },
    keyToLabel(key) {
      key = key.replace(/Count$/, "");
      return capitalCase(key);
    },
  },
};
</script>

<style scoped lang="scss">
#schemaDoc {
  font-size: small;
  color: rgb(var(--v-theme-textSecondary));
  background-color: rgb(var(--v-theme-background));
}

#schemaDoc > td {
  padding-top: 15px;
  border-bottom: none !important;
}

// Hack this component into a table row

:deep(.clipboard) {
  display: table-row;
}

:deep(.clipboard *) {
  height: 52px;
}

:deep(.clipboard > h3) {
  display: table-cell;
  font-weight: normal;
  font-size: 14px;
  padding-left: 16px;
}

:deep(.clipboard > .bodyText) {
  display: table-cell;
  padding-right: 16px;
}
</style>

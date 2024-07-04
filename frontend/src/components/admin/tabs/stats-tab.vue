<template>
  <div v-if="stats" id="stats">
    <StatsTable title="Platform" :items="platformTable" />
    <StatsTable title="Config" :items="configTable">
      <tbody>
        <tr id="schemaDoc">
          <td colspan="2">
            The only endpoint accessible by API Key is
            <a
              :href="`${apiSchemaURL}#/api/api_v3_admin_stats_retrieve`"
              target="_blank"
              >/admin/stats</a
            >
          </td>
        </tr>
        <tr>
          <td colspan="2">
            <ConfirmDialog
              button-text="Regenerate API Key"
              title-text="Regenerate"
              object-name="API Key"
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
import { mdiClipboardCheckOutline, mdiClipboardOutline } from "@mdi/js";
import { snakeCase, startCase } from "lodash";
import { mapActions, mapState } from "pinia";

import StatsTable from "@/components/admin/tabs/stats-table.vue";
import ConfirmDialog from "@/components/confirm-dialog.vue";
import { copyToClipboard } from "@/copy-to-clipboard";
import { useAdminStore } from "@/stores/admin";
import { useCommonStore } from "@/stores/common";

const API_TOOLTIP = "Copy API Key to clipboard";
import CHOICES from "@/choices.json";

const vueToLookup = (choices) => {
  const lookup = {};
  for (const choice of choices) {
    lookup[choice.value] = choice.title;
  }
  return lookup;
};

const LOOKUPS = {
  topGroup: CHOICES.browser.groupNames,
  orderBy: vueToLookup(CHOICES.browser.orderBy),
  fitTo: vueToLookup(CHOICES.reader.fitTo),
  readingDirection: vueToLookup(CHOICES.reader.readingDirection),
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
  "storyArcNumbersCount",
  "identifierTypesCount",
  "contributorPersonsCount",
  "contributorRolesCount",
]);
Object.freeze(INDENT_KEYS);

export default {
  name: "AdminTasksTab",
  components: {
    ConfirmDialog,
    StatsTable,
  },
  data() {
    return {
      showTooltip: { show: false },
      apiSchemaURL: window.CODEX.API_V3_PATH,
    };
  },
  computed: {
    ...mapState(useCommonStore, {}),
    ...mapState(useAdminStore, {
      stats: (state) => state.stats,
    }),
    clipBoardEnabled() {
      return location.prototcal == "https:";
    },
    apiTooltip() {
      return API_TOOLTIP ? this.clipBoardEnabled : undefined;
    },
    clipBoardIcon() {
      return this.showTooltip ? mdiClipboardCheckOutline : mdiClipboardOutline;
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
      let apiKeyValue = "";
      for (const [key, value] of Object.entries(this.stats?.config)) {
        let label;
        if (key == "apiKey") {
          apiKeyValue = value;
          continue;
        } else {
          label = CONFIG_LABELS[key];
        }
        table[label] = value;
      }
      table["API Key"] = apiKeyValue;
      return table;
    },
    userSettingsTable() {
      const table = {};
      for (const [key, countObj] of Object.entries(this.stats?.sessions)) {
        const countTable = {};
        const lookup = LOOKUPS[key];
        for (const [typeKey, count] of Object.entries(countObj)) {
          let typeLabel;
          if (lookup) {
            typeLabel = lookup[snakeCase(typeKey)];
          } else {
            typeLabel = typeKey;
          }
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
        const label = this.keyToLabel(key) + "s";
        table[label] = value;
      }
      return table;
    },
    fileTypesTable() {
      const table = {};
      for (const [key, value] of Object.entries(this.stats?.fileTypes)) {
        const label = this.keyToLabel(key).toUpperCase();
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
    onClickAPIKey() {
      if (!this.clipBoardEnabled) {
        return;
      }
      copyToClipboard(this.stats.config.apiKey, this.showTooltip);
    },
    keyToLabel(key) {
      key = key.replace(/Count$/, "");
      return startCase(key);
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

#schemaDoc>td {
  border-bottom: none !important;
}
</style>

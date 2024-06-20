<template>
  <div v-if="stats" id="stats">
    <StatsTable title="Platform" :items="platformTable" />
    <StatsTable title="Config" :items="configTable" />
    <StatsTable title="User Settings" :items="userSettingsTable" />
    <StatsTable title="Browser Groups" :items="browserGroupsTable" />
    <StatsTable title="File Types" :items="fileTypesTable" />
    <StatsTable title="Metadata" :items="metadataTable" />
  </div>
  <div id="apiBlock">
    <ConfirmDialog
      button-text="Regenerate API Key"
      title-text="Regenerate"
      object-name="API Key"
      confirm-text="Regenerate"
      @confirm="regenAPIKey"
    />
    <p id="schemaDoc">
      The only endpoint accessible by API Key is
      <a
        :href="`${apiSchemaURL}#/api/api_v3_admin_stats_retrieve`"
        target="_blank"
        >/admin/stats</a
      >
    </p>
  </div>
</template>

<script>
import { mdiClipboardCheckOutline, mdiClipboardOutline } from "@mdi/js";
import _ from "lodash";
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
        let labelValue = value;
        if (key === "system") {
          labelValue += " " + this.stats.platform.systemRelease;
        } else if (key === "systemRelease") {
          continue;
        }
        const label = this.keyToLabel(key);
        table[label] = labelValue;
      }
      return table;
    },
    configTable() {
      const table = {};
      for (const [key, value] of Object.entries(this.stats?.config)) {
        let label;
        if (key == "apiKey") {
          label = "API Key";
        } else {
          label = this.keyToLabel(key);
        }
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
          if (lookup) {
            typeLabel = lookup[_.snakeCase(typeKey)];
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
        const label = this.keyToLabel(key);
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
        let label = this.keyToLabel(key);
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
      return _.startCase(key);
    },
  },
};
</script>

<style scoped lang="scss">
#apiBlock {
  display: inline-block;
  vertical-align: top;
  max-width: 200px;
  margin-top: 30px;
}

#schemaDoc {
  color: rgb(var(--v-theme-textSecondary));
  font-size: small;
}
</style>

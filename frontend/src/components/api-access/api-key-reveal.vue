<template>
  <div class="apiKeyReveal">
    <ClipBoard
      tooltip="Copy key to clipboard"
      :title="`Key for ${name}`"
      subtitle="Copy it now: it is shown only this once."
      :text="apiKey"
    />
    <table v-if="usage.length" class="usageTable">
      <tbody>
        <tr v-for="row in usage" :key="row.api">
          <td class="usageApi">{{ row.api }}</td>
          <td class="usageValue">
            <template v-if="row.api === 'Stats'">
              <code>{{ statsUrl }}?apiKey={{ apiKey }}</code
              >, or the header
              <code>Authorization: Bearer {{ apiKey }}</code>
            </template>
            <template v-else-if="row.api === 'OPDS'">
              Username <b>{{ username }}</b> with this key as the password, or
              the header <code>Authorization: Bearer {{ apiKey }}</code>
            </template>
            <template v-else>
              Username <b>{{ username }}</b> with this key as the password
            </template>
          </td>
        </tr>
      </tbody>
    </table>
    <p v-if="note" class="apiKeyNote">{{ note }}</p>
  </div>
</template>

<script>
import { V4_BASE } from "@/api/v4/base";
import ClipBoard from "@/components/clipboard.vue";

const NO_READER_API =
  "No reader API is turned on for this server, so this key logs in nowhere" +
  " until an admin turns on OPDS or KOReader Sync.";
const STATS_OFF =
  "Stats API Keys is turned off on this server, so this key logs in nowhere" +
  " until an admin turns it on in Admin Settings.";

export default {
  name: "ApiKeyReveal",
  components: {
    ClipBoard,
  },
  props: {
    apiKey: { type: String, required: true },
    name: { type: String, required: true },
    scope: { type: String, required: true },
    username: { type: String, default: "" },
    // Paths by API, from /api-urls. An API that is off is absent.
    urls: { type: Object, required: true },
  },
  computed: {
    isStats() {
      return this.scope === "stats";
    },
    usage() {
      if (this.isStats) {
        return [{ api: "Stats" }];
      }
      const rows = [];
      if (this.urls.opdsV1) {
        rows.push({ api: "OPDS" });
      }
      if (this.urls.koreader) {
        rows.push({ api: "KOReader" });
      }
      return rows;
    },
    statsUrl() {
      const path = this.urls.stats || `${V4_BASE}admin/stats`;
      return globalThis.location.origin + path;
    },
    note() {
      if (this.isStats) {
        return this.urls.stats ? "" : STATS_OFF;
      }
      return this.usage.length ? "" : NO_READER_API;
    },
  },
};
</script>

<style scoped lang="scss">
.apiKeyReveal {
  display: flex;
  flex-direction: column;
  gap: 0.5em;
}

.usageTable {
  width: 100%;
}

.usageTable td {
  padding: 4px;
  vertical-align: top;
}

.usageApi {
  white-space: nowrap;
}

.usageValue {
  border-radius: 5px;
  background-color: rgb(var(--v-theme-surface));
  overflow-wrap: anywhere;
}

.apiKeyNote {
  color: rgb(var(--v-theme-warning));
}
</style>

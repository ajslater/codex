<template>
  <div class="apiKeyReveal">
    <!-- Highlighted: the key is never shown again. -->
    <p class="revealWarning">
      <v-icon :icon="mdiAlertOutline" size="small" />
      Copy it now: it is shown only this once.
    </p>
    <ClipBoard
      class="revealKey"
      tooltip="Copy key to clipboard"
      :title="`Key for ${name}`"
      :text="apiKey"
    />
    <p v-if="isStats" class="usage">
      Request <code>{{ statsUrl }}?apiKey={{ apiKey }}</code
      >, or send the header <code>Authorization: Bearer {{ apiKey }}</code
      >.
    </p>
    <!-- One line for OPDS and KOReader alike; only OPDS takes a header. -->
    <p v-else-if="readerApiOn" class="usage">
      Log in with username <b>{{ username }}</b> and this key as the
      password<template v-if="urls?.opdsV1"
        >, or send the header
        <code>Authorization: Bearer {{ apiKey }}</code></template
      >.
    </p>
    <p v-if="note" class="apiKeyNote">{{ note }}</p>
  </div>
</template>

<script>
import { mdiAlertOutline } from "@mdi/js";

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
    /*
     * Paths by API, from /api-urls. An API that is off is absent.
     * Undefined until they load.
     */
    urls: { type: Object, default: undefined },
  },
  data() {
    return { mdiAlertOutline };
  },
  computed: {
    isStats() {
      return this.scope === "stats";
    },
    readerApiOn() {
      return Boolean(this.urls?.opdsV1 || this.urls?.koreader);
    },
    statsUrl() {
      const path = this.urls?.stats || `${V4_BASE}admin/stats`;
      return globalThis.location.origin + path;
    },
    note() {
      // Which APIs are on is unknown until the URLs load.
      if (!this.urls) {
        return "";
      }
      if (this.isStats) {
        return this.urls.stats ? "" : STATS_OFF;
      }
      return this.readerApiOn ? "" : NO_READER_API;
    },
  },
};
</script>

<style scoped lang="scss">
.apiKeyReveal {
  display: flex;
  flex-direction: column;
  gap: 0.5em;
  padding: 12px;
  border: 2px solid rgb(var(--v-theme-primary));
  border-radius: 6px;
  background-color: rgba(var(--v-theme-primary), 0.08);
}

.revealWarning {
  margin: 0;
  font-weight: bold;
  color: rgb(var(--v-theme-primary));
}

.revealKey :deep(.bodyText) {
  font-family: monospace;
  font-size: 1.1em;
  color: rgb(var(--v-theme-text-primary));
  overflow-wrap: anywhere;
}

.usage {
  margin: 0;
  padding: 4px;
  border-radius: 5px;
  background-color: rgb(var(--v-theme-surface));
  overflow-wrap: anywhere;
}

.apiKeyNote {
  color: rgb(var(--v-theme-warning));
}
</style>

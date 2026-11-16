<template>
  <!-- One banded block per API: its URL and whatever explains it. -->
  <div v-if="rows.length" class="apiUrls">
    <div v-for="row in rows" :key="row.key" class="apiUrlBlock">
      <ClipBoard
        :title="row.title"
        :subtitle="row.subtitle"
        tooltip="Copy URL to clipboard"
        :text="row.url"
      />
      <!-- Outside the ClipBoard: a click anywhere on it copies the URL. -->
      <p v-if="row.key === 'opdsV2'" class="apiUrlNote">
        Supported in newer clients such as
        <a href="https://www.stumpapp.dev/" target="_blank"
          >Stump<v-icon size="small">{{ mdiOpenInNew }}</v-icon></a
        >
        and
        <a href="https://readest.com/" target="_blank"
          >Readest<v-icon size="small">{{ mdiOpenInNew }}</v-icon></a
        >.
      </p>
      <KOReaderHelp
        v-if="row.key === 'koreader'"
        class="apiUrlHelp"
        :username="username"
      />
    </div>
  </div>
  <p v-else class="apiUrlsNone">No APIs are turned on for this server.</p>
</template>

<script>
import { mdiOpenInNew } from "@mdi/js";

import KOReaderHelp from "@/components/api-access/koreader-help.vue";
import ClipBoard from "@/components/clipboard.vue";

// The order the URLs show in, and how each is titled.
const API_ROWS = Object.freeze([
  Object.freeze({ key: "opdsV1", title: "OPDS v1.2", subtitle: "" }),
  Object.freeze({ key: "opdsV2", title: "OPDS v2.0", subtitle: "" }),
  Object.freeze({ key: "koreader", title: "KOReader Sync", subtitle: "" }),
  Object.freeze({ key: "stats", title: "Stats API", subtitle: "Admins only" }),
]);

export default {
  name: "ApiUrls",
  components: {
    ClipBoard,
    KOReaderHelp,
  },
  props: {
    // Paths by API, from /api-urls. An API that is off is absent.
    urls: { type: Object, required: true },
    username: { type: String, default: "" },
  },
  data() {
    return { mdiOpenInNew };
  },
  computed: {
    rows() {
      const origin = globalThis.location.origin;
      return API_ROWS.filter((row) => this.urls[row.key]).map((row) => ({
        ...row,
        url: origin + this.urls[row.key],
      }));
    },
  },
};
</script>

<style scoped lang="scss">
.apiUrls {
  display: flex;
  flex-direction: column;
}

.apiUrlBlock {
  padding: 8px;
  border-radius: 4px;
}

// Alternating bands, as the admin key/value tables wear them.
.apiUrlBlock:nth-child(even) {
  background-color: rgba(var(--v-theme-on-surface), 0.05);
}

.apiUrlNote {
  margin-top: 2px;
  font-size: small;
  color: rgb(var(--v-theme-text-secondary));
}

.apiUrlHelp {
  margin-top: 8px;
}

.apiUrlsNone {
  color: rgb(var(--v-theme-text-disabled));
}
</style>

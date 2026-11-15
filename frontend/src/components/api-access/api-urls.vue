<template>
  <section class="apiUrls">
    <template v-if="rows.length">
      <template v-for="row in rows" :key="row.key">
        <ClipBoard
          class="apiUrl"
          :title="row.title"
          :subtitle="row.subtitle"
          tooltip="Copy URL to clipboard"
          :text="row.url"
        />
        <KOReaderHelp v-if="row.key === 'koreader'" :username="username" />
      </template>
    </template>
    <p v-else class="apiUrlsNone">No APIs are turned on for this server.</p>
  </section>
</template>

<script>
import KOReaderHelp from "@/components/api-access/koreader-help.vue";
import ClipBoard from "@/components/clipboard.vue";

// The order the URLs show in, and how each is titled.
const API_ROWS = Object.freeze([
  Object.freeze({ key: "opdsV1", title: "OPDS v1.2", subtitle: "" }),
  Object.freeze({
    key: "opdsV2",
    title: "OPDS v2.0",
    subtitle: "Supported in newer clients (like Stump)",
  }),
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
  gap: 0.5em;
}

.apiUrl {
  padding: 5px;
}

.apiUrlsNone {
  color: rgb(var(--v-theme-text-disabled));
}
</style>

<template>
  <div>
    <div v-if="loadError" class="apiKeyListError">
      <p>{{ loadError }}</p>
      <v-btn variant="text" text="Retry" @click="loadApiKeys" />
    </div>
    <div v-else-if="apiKeys.length" class="apiKeyListScroll">
      <table class="apiKeyList">
        <thead>
          <tr>
            <th>Name</th>
            <th v-if="showAccess">Access</th>
            <th>Key</th>
            <th>Last used</th>
            <th />
          </tr>
        </thead>
        <tbody>
          <template v-for="row in apiKeys" :key="row.pk">
            <tr>
              <td>{{ row.name }}</td>
              <td v-if="showAccess">{{ accessLabel(row) }}</td>
              <td class="keyPrefix">{{ row.prefix }}…</td>
              <td>{{ lastUsed(row) }}</td>
              <td>
                <ConfirmDialog
                  :icon="mdiKeyRemove"
                  size="small"
                  density="compact"
                  variant="text"
                  :title-text="`Revoke ${row.name}`"
                  :text="revokeText(row)"
                  confirm-text="Revoke"
                  @confirm="revoke(row)"
                />
              </td>
            </tr>
            <tr v-if="row.scope === 'universal'" class="universalHint">
              <td :colspan="showAccess ? 5 : 4">{{ UNIVERSAL_HINT }}</td>
            </tr>
          </template>
        </tbody>
      </table>
    </div>
    <p v-else class="apiKeyListEmpty">No API keys yet.</p>
    <p v-if="revokeError" class="apiKeyListError">{{ revokeError }}</p>
  </div>
</template>

<script>
import { mdiKeyRemove } from "@mdi/js";
import { mapActions } from "pinia";

import ConfirmDialog from "@/components/confirm-dialog.vue";
import { getDateTime } from "@/datetime";
import { useAuthStore } from "@/stores/auth";

// What each scope logs in to.
const ACCESS_LABELS = Object.freeze({
  device: "OPDS · KOReader",
  universal: "Everything (legacy)",
  stats: "Stats",
});
const NOT_SINCE_UPGRADE = "Not since upgrade";
const UNIVERSAL_HINT =
  "Your old Authorization Bearer Token. It still logs in everywhere, but it" +
  " can no longer be shown or made again. Replace it with Device Keys, then" +
  " revoke it.";

export default {
  name: "ApiKeyList",
  components: {
    ConfirmDialog,
  },
  props: {
    apiKeys: { type: Array, required: true },
    /*
     * Only admins can hold more than one kind of key worth telling apart:
     * everyone else makes device keys, with at most a migrated Universal
     * Token, whose row explains itself.
     */
    showAccess: { type: Boolean, default: false },
    // Why the list failed to load: an empty list would read as no keys.
    loadError: { type: String, default: "" },
  },
  emits: ["revoked"],
  data() {
    return {
      mdiKeyRemove,
      UNIVERSAL_HINT,
      revokeError: "",
    };
  },
  methods: {
    ...mapActions(useAuthStore, ["deleteApiKey", "loadApiKeys"]),
    async revoke(row) {
      this.revokeError = "";
      if (await this.deleteApiKey(row.pk)) {
        this.$emit("revoked", row);
      } else {
        this.revokeError = `Could not revoke ${row.name}.`;
      }
    },
    accessLabel(row) {
      return Reflect.get(ACCESS_LABELS, row.scope) ?? row.scope;
    },
    lastUsed(row) {
      if (row.lastUsedAt) {
        return getDateTime(row.lastUsedAt);
      }
      // Codex recorded no use of the old bearer tokens before the upgrade
      // that made them Universal Tokens, so "Never" would be wrong.
      return row.scope === "universal" ? NOT_SINCE_UPGRADE : "Never";
    },
    revokeText(row) {
      const text = `Anything using ${row.name} is logged out.`;
      return row.scope === "universal"
        ? `${text} A Universal Token cannot be made again.`
        : text;
    },
  },
};
</script>

<style scoped lang="scss">
.apiKeyListScroll {
  overflow-x: auto;
}

.apiKeyList {
  width: 100%;
  border-collapse: collapse;
}

.apiKeyList th {
  text-align: left;
  color: rgb(var(--v-theme-text-disabled));
}

.apiKeyList td,
.apiKeyList th {
  padding: 4px;
}

.keyPrefix {
  font-family: monospace;
}

.universalHint td {
  padding-top: 0;
  font-size: small;
  color: rgb(var(--v-theme-text-secondary));
}

.apiKeyListEmpty {
  color: rgb(var(--v-theme-text-disabled));
}

.apiKeyListError {
  color: rgb(var(--v-theme-error));
}
</style>

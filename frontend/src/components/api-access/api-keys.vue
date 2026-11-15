<template>
  <section class="apiKeys">
    <h3 class="apiKeysTitle">API Keys</h3>
    <p class="apiKeysHelp">
      {{ DEVICE_HELP }}
      <template v-if="isUserAdmin">{{ STATS_HELP }}</template>
    </p>
    <ApiKeyList :api-keys="apiKeys" />
    <ApiKeyReveal
      v-if="created"
      :api-key="created.key"
      :name="created.name"
      :scope="created.scope"
      :username="username"
      :urls="urls"
    />
    <ApiKeyCreate :is-admin="isUserAdmin" @created="created = $event" />
  </section>
</template>

<script>
import { mapActions, mapState } from "pinia";

import ApiKeyCreate from "@/components/api-access/api-key-create.vue";
import ApiKeyList from "@/components/api-access/api-key-list.vue";
import ApiKeyReveal from "@/components/api-access/api-key-reveal.vue";
import { useAuthStore } from "@/stores/auth";
import { useCommonStore } from "@/stores/common";

const DEVICE_HELP =
  "Give each reader app or device its own Device Key. It logs in to OPDS" +
  " and KOReader sync only, and can be revoked on its own.";
const STATS_HELP =
  "A Stats key reads the admin Stats API, as you, while you are an admin.";

export default {
  name: "ApiKeys",
  components: {
    ApiKeyCreate,
    ApiKeyList,
    ApiKeyReveal,
  },
  props: {
    // Paths by API, from /api-urls, so the new key's help names only APIs
    // that are on.
    urls: { type: Object, required: true },
  },
  data() {
    return {
      DEVICE_HELP,
      STATS_HELP,
      // The key just made, ``{key, name, scope}``: shown once, never again.
      created: undefined,
    };
  },
  computed: {
    ...mapState(useAuthStore, ["apiKeys", "isUserAdmin", "user"]),
    username() {
      return this.user?.username || "";
    },
  },
  mounted() {
    // A fresh dialog: drop errors from an earlier attempt.
    this.clearErrors();
  },
  methods: {
    ...mapActions(useCommonStore, ["clearErrors"]),
  },
};
</script>

<style scoped lang="scss">
.apiKeys {
  display: flex;
  flex-direction: column;
  gap: 0.5em;
}

.apiKeysTitle {
  margin: 0;
}

.apiKeysHelp {
  color: rgb(var(--v-theme-text-disabled));
}
</style>

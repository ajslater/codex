<template>
  <v-form class="apiKeyCreate" @submit.prevent="create">
    <v-text-field
      v-model="name"
      class="apiKeyName"
      label="New key name"
      placeholder="Kobo Libra"
      :counter="NAME_MAX_LENGTH"
      :maxlength="NAME_MAX_LENGTH"
      :error-messages="nameErrors"
      density="compact"
      clearable
      @update:model-value="nameError = ''"
    />
    <v-select
      v-if="isAdmin"
      v-model="scope"
      class="apiKeyScope"
      label="Kind"
      :items="SCOPE_ITEMS"
      density="compact"
      hide-details
    />
    <v-btn
      type="submit"
      :prepend-icon="mdiKeyPlus"
      text="Create"
      :loading="creating"
    />
  </v-form>
</template>

<script>
import { mdiKeyPlus } from "@mdi/js";
import { mapActions } from "pinia";

import SCOPE_TITLES from "@/choices/api-key-scopes.json";
import LIMITS from "@/choices/limits.json";
import { useAuthStore } from "@/stores/auth";
import { getErrors } from "@/stores/common";

// The scopes a user can make: universal keys are only ever migrated.
const SCOPE_ITEMS = Object.freeze(
  ["device", "stats"].map((value) =>
    Object.freeze({ value, title: Reflect.get(SCOPE_TITLES, value) }),
  ),
);
const DEFAULT_SCOPE = "device";
const NAME_REQUIRED = "Name the key, for example after the device it is for.";

export default {
  name: "ApiKeyCreate",
  props: {
    isAdmin: { type: Boolean, default: false },
  },
  emits: ["created"],
  data() {
    return {
      mdiKeyPlus,
      NAME_MAX_LENGTH: LIMITS.apiKeyNameMaxLength,
      SCOPE_ITEMS,
      name: "",
      scope: DEFAULT_SCOPE,
      nameError: "",
      // The server's refusal, kept here: the shared form errors show in the
      // Profile dialog underneath.
      createErrors: [],
      creating: false,
    };
  },
  computed: {
    nameErrors() {
      return this.nameError ? [this.nameError] : this.createErrors;
    },
  },
  methods: {
    ...mapActions(useAuthStore, ["createApiKey"]),
    async create() {
      // A double-click must not make two keys.
      if (this.creating) {
        return;
      }
      const name = this.name?.trim() || "";
      if (!name) {
        this.nameError = NAME_REQUIRED;
        return;
      }
      const scope = this.isAdmin ? this.scope : DEFAULT_SCOPE;
      this.creating = true;
      try {
        const key = await this.createApiKey({ name, scope });
        this.createErrors = [];
        this.$emit("created", { key, name, scope });
        this.name = "";
        this.scope = DEFAULT_SCOPE;
      } catch (error) {
        this.createErrors = getErrors(error);
      } finally {
        this.creating = false;
      }
    },
  },
};
</script>

<style scoped lang="scss">
.apiKeyCreate {
  display: flex;
  flex-wrap: wrap;
  gap: 0.5em;
  align-items: baseline;
}

.apiKeyName {
  flex: 1 1 200px;
}

.apiKeyScope {
  flex: 0 0 120px;
}
</style>

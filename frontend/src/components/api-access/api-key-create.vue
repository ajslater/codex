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
    <v-btn type="submit" :prepend-icon="mdiKeyPlus" text="Create" />
  </v-form>
</template>

<script>
import { mdiKeyPlus } from "@mdi/js";
import { mapActions, mapState } from "pinia";

import SCOPE_TITLES from "@/choices/api-key-scopes.json";
import LIMITS from "@/choices/limits.json";
import { useAuthStore } from "@/stores/auth";
import { useCommonStore } from "@/stores/common";

// The scopes a user can make: universal keys are only ever migrated.
const SCOPE_ITEMS = Object.freeze(
  ["device", "stats"].map((value) =>
    Object.freeze({ value, title: Reflect.get(SCOPE_TITLES, value) }),
  ),
);
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
      scope: "device",
      nameError: "",
    };
  },
  computed: {
    ...mapState(useCommonStore, {
      formErrors: (state) => state.form.errors,
    }),
    nameErrors() {
      return this.nameError ? [this.nameError] : this.formErrors;
    },
  },
  methods: {
    ...mapActions(useAuthStore, ["createApiKey"]),
    async create() {
      const name = this.name?.trim() || "";
      if (!name) {
        this.nameError = NAME_REQUIRED;
        return;
      }
      const scope = this.isAdmin ? this.scope : "device";
      const key = await this.createApiKey({ name, scope });
      if (key) {
        this.$emit("created", { key, name, scope });
        this.name = "";
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

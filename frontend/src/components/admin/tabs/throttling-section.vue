<!--
  Throttling lives as a section on the Settings tab rather than its
  own tab — its admin surface is small enough that a dedicated tab
  was overkill. The outer ``adminContainer`` belongs to the parent
  (settings-tab.vue); this component renders just the group.
-->
<template>
  <div v-if="!settings" class="adminGroup">
    <v-progress-circular indeterminate />
  </div>
  <v-form v-else ref="form" @submit.prevent="saveDraft">
    <div class="adminGroup">
      <div class="adminGroupHeader">
        <h3>Throttling</h3>
        <p class="adminGroupHint">
          Set to 0 to disable rate limiting for that scope.
        </p>
      </div>
      <div v-for="scope in scopes" :key="scope.key" class="adminCard">
        <div class="adminCardHeader">
          <div class="adminCardInfo">
            <div class="adminCardTitle">{{ scope.title }}</div>
            <div class="adminCardDesc">{{ scope.desc }}</div>
          </div>
          <div class="adminCardActions">
            <v-text-field
              v-model.number="draft[scope.key]"
              type="number"
              min="0"
              max="65535"
              :label="scope.unit"
              :rules="rangeRules"
              hide-details="auto"
              density="compact"
              class="throttleField"
            />
          </div>
        </div>
      </div>
      <div class="settingsActions">
        <v-btn
          type="submit"
          variant="tonal"
          size="small"
          :loading="saving"
          :disabled="!hasChanges"
        >
          Save Throttling
        </v-btn>
        <v-btn
          variant="text"
          size="small"
          :disabled="!hasChanges || saving"
          @click="resetDraft"
        >
          Revert
        </v-btn>
      </div>
    </div>
  </v-form>
</template>

<script>
import { dequal } from "dequal";
import { mapActions, mapState } from "pinia";

import { useAdminStore } from "@/stores/admin";

const SCOPES = Object.freeze([
  {
    key: "anon",
    title: "Anonymous Users",
    desc: "API requests from anonymous (not logged-in) clients.",
    unit: "Requests / minute",
  },
  {
    key: "user",
    title: "Authenticated Users",
    desc: "API requests from logged-in users.",
    unit: "Requests / minute",
  },
  {
    key: "opds",
    title: "OPDS Feed",
    desc: "OPDS browser and catalog endpoints.",
    unit: "Requests / minute",
  },
  {
    key: "opensearch",
    title: "OpenSearch",
    desc: "OpenSearch description document.",
    unit: "Requests / minute",
  },
  {
    key: "resetPassword",
    title: "Password Reset",
    desc: "Outbound password-reset link requests.",
    unit: "Requests / hour",
  },
]);
const SCOPE_KEYS = SCOPES.map((s) => s.key);
const MAX_RATE = 65_535;

function pickFields(source) {
  const out = {};
  for (const key of SCOPE_KEYS) {
    const value = Number(source?.[key]);
    out[key] = Number.isFinite(value) ? value : 0;
  }
  return out;
}

export default {
  name: "AdminThrottlingSection",
  data() {
    return {
      scopes: SCOPES,
      draft: pickFields(undefined),
      saving: false,
    };
  },
  computed: {
    ...mapState(useAdminStore, {
      settings: (state) => state.throttleSettings,
    }),
    hasChanges() {
      return !dequal(this.draft, pickFields(this.settings));
    },
    rangeRules() {
      return [
        (v) => {
          if (v === "" || v === null || v === undefined) return true;
          const n = Number(v);
          return (
            (Number.isInteger(n) && n >= 0 && n <= MAX_RATE) ||
            `Must be 0–${MAX_RATE}`
          );
        },
      ];
    },
  },
  watch: {
    settings: {
      immediate: true,
      handler(value) {
        this.draft = pickFields(value);
      },
    },
  },
  mounted() {
    this.loadThrottleSettings();
  },
  methods: {
    ...mapActions(useAdminStore, [
      "loadThrottleSettings",
      "updateThrottleSettings",
    ]),
    resetDraft() {
      this.draft = pickFields(this.settings);
    },
    async saveDraft() {
      const form = this.$refs.form;
      if (form) {
        const { valid } = await form.validate();
        if (!valid) return;
      }
      this.saving = true;
      try {
        await this.updateThrottleSettings({ ...this.draft });
      } finally {
        this.saving = false;
      }
    },
  },
};
</script>

<style scoped lang="scss">
@use "@/components/admin/tabs/admin-section.scss";

.adminGroupHint {
  font-size: 0.85em;
  color: rgb(var(--v-theme-textSecondary));
  margin-top: 4px;
}

.throttleField {
  width: 200px;
}

.settingsActions {
  display: flex;
  gap: 8px;
  align-items: center;
  margin-top: 16px;
}
</style>

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
  <div v-else class="adminGroup">
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
            :model-value="settings[scope.key]"
            type="number"
            min="0"
            max="65535"
            :label="scope.unit"
            hide-details="auto"
            density="compact"
            class="throttleField"
            @update:model-value="save(scope.key, $event)"
          />
        </div>
      </div>
    </div>
  </div>
</template>

<script>
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

export default {
  name: "AdminThrottlingSection",
  data() {
    return {
      scopes: SCOPES,
    };
  },
  computed: {
    ...mapState(useAdminStore, {
      settings: (state) => state.throttleSettings,
    }),
  },
  mounted() {
    this.loadThrottleSettings();
  },
  methods: {
    ...mapActions(useAdminStore, [
      "loadThrottleSettings",
      "updateThrottleSettings",
    ]),
    save(field, value) {
      const n = Number.parseInt(value, 10);
      const sanitized = Number.isFinite(n) && n >= 0 ? n : 0;
      this.updateThrottleSettings({ [field]: sanitized });
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
</style>

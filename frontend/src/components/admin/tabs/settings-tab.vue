<template>
  <div id="settings" class="adminContainer">
    <template v-for="group in groupedFlags" :key="group.title">
      <div class="adminGroup">
        <div class="adminGroupHeader">
          <h3>{{ group.title }}</h3>
        </div>
        <FlagCard v-for="key in group.keys" :key="`f${key}`" :item-key="key" />
      </div>
      <!--
        Throttling lives between Tags Import and System per the
        Settings-page layout. ``flag-groups.json`` keeps its own
        ordering so adding new flag groups doesn't change throttle
        placement.
      -->
      <ThrottlingSection v-if="group.title === 'Tags Import'" />
    </template>

    <!--
      API Key sits at the bottom because it is rarely touched after
      initial setup. The only endpoint that accepts it is
      ``/admin/stats``, so an admin who is here for a flag change
      does not have to scroll past it.
    -->
    <div class="adminGroup">
      <div class="adminGroupHeader">
        <h3>API Key</h3>
      </div>
      <div class="adminCard apiKeyCard">
        <ClipBoard
          v-if="apiKey"
          tooltip="Copy API Key"
          title="API Key"
          :text="apiKey"
        />
        <div class="apiKeyHint">
          The only endpoint accessible by API Key is
          <!-- eslint-disable-next-line sonarjs/no-vue-bypass-sanitization -->
          <a :href="schemaHref" target="_blank">/admin/stats</a>.
        </div>
        <ConfirmDialog
          button-text="Regenerate API Key"
          title-text="Regenerate"
          text="API Key"
          confirm-text="Regenerate"
          @confirm="regenAPIKey"
        />
      </div>
    </div>
  </div>
</template>

<script>
import { mapActions, mapState } from "pinia";

import FlagCard from "@/components/admin/tabs/flag-card.vue";
import ADMIN_FLAG_GROUPS from "@/components/admin/tabs/flag-groups.json";
import ThrottlingSection from "@/components/admin/tabs/throttling-section.vue";
import ClipBoard from "@/components/clipboard.vue";
import ConfirmDialog from "@/components/confirm-dialog.vue";
import { useAdminStore } from "@/stores/admin";

// Keys whose UI lives on a different tab or its own section — render
// them in their dedicated place and skip the generic flag-card grid
// so the user sees one card per flag, in one place. Mirrors:
//   - RG/RV/NU/AA/AR → Users tab
//   - CM → Custom Covers tab
//   - AK → API Key section at the bottom of this tab
const TAB_HIDDEN_KEYS = new Set(["AA", "AK", "AR", "CM", "NU", "RG", "RV"]);

export default {
  name: "AdminSettingsTab",
  components: {
    ClipBoard,
    ConfirmDialog,
    FlagCard,
    ThrottlingSection,
  },
  data() {
    return {
      schemaHref: "/api/v4/schema",
    };
  },
  computed: {
    ...mapState(useAdminStore, {
      flags: (state) => state.flags,
      apiKey: (state) => state.apiKey,
    }),
    groupedFlags() {
      /*
       * Filter ``ADMIN_FLAG_GROUPS`` down to the keys actually
       * rendered on this tab. Each entry keeps its full key list so
       * the order in flag-groups.json drives ordering — moved keys
       * (see ``TAB_HIDDEN_KEYS``) are dropped here rather than from
       * the JSON, which still describes the canonical grouping for
       * any future location decisions.
       */
      const flagKeys = new Set((this.flags || []).map((f) => f.key));
      const groups = [];
      for (const group of ADMIN_FLAG_GROUPS) {
        const keys = group.keys.filter(
          (k) => flagKeys.has(k) && !TAB_HIDDEN_KEYS.has(k),
        );
        if (keys.length > 0) {
          groups.push({ title: group.title, keys });
        }
      }
      return groups;
    },
  },
  mounted() {
    // ``AgeRatingMetron`` feeds the AA/AR dropdowns rendered on the
    // Users tab, but FlagCard pulls them from the admin store, so we
    // make sure they're loaded here too. The API key is its own
    // small endpoint to avoid re-loading the full stats payload.
    this.loadTables(["Flag", "AgeRatingMetron"]);
    this.loadAPIKey();
  },
  methods: {
    ...mapActions(useAdminStore, ["loadTables", "loadAPIKey", "updateAPIKey"]),
    regenAPIKey() {
      this.updateAPIKey().catch(console.warn);
    },
  },
};
</script>

<style scoped lang="scss">
@use "@/components/admin/tabs/admin-section.scss";

.apiKeyCard {
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.apiKeyHint {
  font-size: 0.85em;
  color: rgb(var(--v-theme-textSecondary));
}
</style>

<template>
  <div id="settings" class="adminReadingColumn">
    <template v-for="group in groupedFlags" :key="group.title">
      <AdminSection :title="group.title">
        <template v-if="group.title === defaultsHintGroup" #hint>
          The default view and the other settings new sessions start with are on
          the
          <router-link :to="{ name: 'admin-defaults' }">Defaults</router-link>
          tab.
        </template>
        <FlagCard v-for="key in group.keys" :key="`f${key}`" :item-key="key" />
      </AdminSection>
      <!--
        Throttling lives between Tags Import and System per the
        Settings-page layout. ``flag-groups.json`` keeps its own
        ordering so adding new flag groups doesn't change throttle
        placement.
      -->
      <ThrottlingSection v-if="group.title === 'Tags Import'" />
    </template>
  </div>
</template>

<script>
import { mapActions, mapState } from "pinia";

import AdminSection from "@/components/admin/tabs/admin-section.vue";
import FlagCard from "@/components/admin/tabs/flag-card.vue";
import ADMIN_FLAG_GROUPS from "@/components/admin/tabs/flag-groups.json";
import ThrottlingSection from "@/components/admin/tabs/throttling-section.vue";
import { useAdminStore } from "@/stores/admin";

// Keys whose UI lives on a different tab or its own section — render
// them in their dedicated place and skip the generic flag-card grid
// so the user sees one card per flag, in one place. Mirrors:
//   - RG/RV/NU/AA/AR → Users tab
//   - CM → Custom Covers tab
const TAB_HIDDEN_KEYS = new Set(["AA", "AR", "CM", "NU", "RG", "RV"]);

export default {
  name: "AdminSettingsTab",
  components: {
    AdminSection,
    FlagCard,
    ThrottlingSection,
  },
  data() {
    return {
      defaultsHintGroup: "Browser Display",
    };
  },
  computed: {
    ...mapState(useAdminStore, {
      flags: (state) => state.flags,
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
    // make sure they're loaded here too.
    this.loadTables(["Flag", "AgeRatingMetron"]);
  },
  methods: {
    ...mapActions(useAdminStore, ["loadTables"]),
  },
};
</script>

<style scoped lang="scss">
@use "@/components/admin/tabs/admin-section.scss";
</style>

<template>
  <div v-if="show">
    <h3 class="blockHeader">Contributors</h3>
    <MetadataTags
      v-for="[roleName, persons] of Object.entries(contributorsDict)"
      :key="roleName"
      :values="persons"
      :label="roleName"
      filter="contributors"
    />
  </div>
</template>

<script>
import { capitalCase } from "change-case-all";

import MetadataTags from "@/components/metadata/metadata-tags.vue";
const ROLE_ORDER = [
  "Creators",
  "Writers",
  "Pencillers",
  "Inkers",
  "Cover Artists",
  "Colorists",
  "Letterers",
  "Editors",
];
Object.freeze(ROLE_ORDER);

export default {
  name: "MetadataContributorsTable",
  components: {
    MetadataTags,
  },
  props: {
    value: {
      type: Array,
      default: undefined,
    },
  },
  computed: {
    contributorsDict() {
      const contributors = {};
      if (!this.value) {
        return contributors;
      }

      // Convert contributors into a role based map
      for (const { role, person } of this.value) {
        const roleName = capitalCase(role.name) + "s";
        if (!contributors[roleName]) {
          contributors[roleName] = [];
        }
        contributors[roleName].push(person);
      }

      // Sort the roles
      let sortedRoles = [];
      const roles = new Set(Object.keys(contributors));
      for (const role of ROLE_ORDER) {
        if (roles.has(role)) {
          sortedRoles.push(role);
          roles.delete(role);
        }
      }
      const tailRoles = Array.from(roles).sort();
      sortedRoles = sortedRoles.concat(tailRoles);

      // Reconstruct the map based on the sorted roles;
      const sortedContributors = {};
      for (const roleName of sortedRoles) {
        const persons = contributors[roleName];
        sortedContributors[roleName] = persons.sort((a, b) =>
          a.name.localeCompare(b.name),
        );
      }

      return sortedContributors;
    },
    show() {
      return Object.keys(this.contributorsDict).length > 0;
    },
  },
};
</script>
<style lang="scss" scoped>
.blockHeader {
  padding: 8px;
  background-color: rgb(var(--v-theme-surface));
  color: rgb(var(--v-theme-textSecondary))
}
</style>

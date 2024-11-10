<template>
  <div v-if="Object.keys(contributorsDict).length > 0">
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
      for (const { role, person } of this.value) {
        const roleName = capitalCase(role.name) + "s";
        if (!contributors[roleName]) {
          contributors[roleName] = [];
        }
        contributors[roleName].push(person);
      }

      const sortedRoles = Object.keys(contributors).sort((a, b) =>
        a.localeCompare(b),
      );
      const sortedContributors = {};
      for (const roleName of sortedRoles) {
        sortedContributors[roleName] = contributors[roleName].sort((a, b) =>
          a.name.localeCompare(b.name),
        );
      }

      return sortedContributors;
    },
  },
};
</script>
<style lang="scss" scoped>
.blockHeader{
  padding: 8px;
  background-color: rgb(var(--v-theme-surface));
  color: rgb(var(--v-theme-textSecondary))
}
</style>

<template>
  <div v-if="Object.keys(contributorsDict).length > 0">
    <h3>Contributors</h3>
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
import MetadataTags from "@/components/metadata/metadata-tags.vue";
import { camelToTitleCase } from "@/to-case";

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
        const roleName = camelToTitleCase(role.name) + "s";
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

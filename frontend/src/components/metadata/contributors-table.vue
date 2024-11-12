<template>
  <div v-if="show">
    <h3 class="blockHeader">Contributors</h3>
    <MetadataTags
      v-for="[roleName, persons] of Object.entries(contributors)"
      :key="roleName"
      :values="persons"
      :label="roleName"
      filter="contributors"
    />
  </div>
</template>

<script>
import MetadataTags from "@/components/metadata/metadata-tags.vue";
import { useMetadataStore } from "@/stores/metadata";

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
    ...mapGetters(useMetadataStore, ["contributors"]),
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

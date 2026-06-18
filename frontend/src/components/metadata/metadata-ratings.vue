<template>
  <v-table v-if="show">
    <tbody>
      <tr v-if="md.criticalRating != null">
        <td class="key">Critical Rating</td>
        <td>
          <MetadataText :value="displayCriticalRating" />
        </td>
      </tr>
      <tr v-if="md.ageRating">
        <td class="key">Age Rating</td>
        <td>
          <MetadataText class="ageRating" :value="displayAgeRating" />
          <MetadataText
            v-if="showOriginalAgeRating"
            class="ageRating originalAgeRating"
            :value="originalAgeRating"
          />
        </td>
      </tr>
    </tbody>
  </v-table>
</template>
<script>
import { mapState } from "pinia";

import MetadataText from "@/components/metadata/metadata-text.vue";
import { useMetadataStore } from "@/stores/metadata";

export default {
  name: "MetadataRatings",
  components: {
    MetadataText,
  },
  computed: {
    ...mapState(useMetadataStore, {
      md: (state) => state.md,
    }),
    show() {
      return this.md?.criticalRating != null || this.md?.ageRating;
    },
    displayCriticalRating() {
      const cr = this.md.criticalRating;
      if (cr == null) return "";
      // Drop trailing zeros (4.0 -> "4"; 4.5 -> "4.5") then suffix scale.
      const n = Number(cr);
      const trimmed = Number.isFinite(n)
        ? n.toFixed(1).replace(/\.0$/, "")
        : String(cr);
      return `${trimmed} / 5`;
    },
    displayAgeRating() {
      const ar = this.md.ageRating;
      return ar.metron?.name || ar.name;
    },
    showOriginalAgeRating() {
      const ar = this.md.ageRating;
      return !!ar.metron?.name && ar.name !== ar.metron.name;
    },
    originalAgeRating() {
      return `(tagged as ${this.md.ageRating.name})`;
    },
  },
};
</script>
<style scoped lang="scss">
@use "vuetify/styles/settings/variables" as vuetify;
@use "sass:map";
@use "./table";

.ageRating {
  display: inline-flex;
}

.originalAgeRating {
  color: rgb(var(--v-theme-textSecondary));
}

@media #{map.get(vuetify.$display-breakpoints, 'sm-and-down')} {
  .key {
    font-size: x-small;
    padding-right: 3px !important;
  }
}
</style>

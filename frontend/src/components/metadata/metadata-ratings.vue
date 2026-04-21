<template>
  <v-table v-if="show">
    <tbody>
      <tr v-if="md.criticalRating">
        <td class="key">Critical Rating</td>
        <td>
          <MetadataText :value="md.criticalRating" />
        </td>
      </tr>
      <tr v-if="md.metronAgeRating">
        <td class="key">Age Rating</td>
        <td>
          <MetadataText class="ageRating" :value="md.metronAgeRating" />
          <MetadataText
            v-if="md.ageRating && md.ageRating.name != md.metronAgeRating"
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
      return (
        this.md?.criticRating !== undefined ||
        this.md?.ageRating ||
        this.md?.metronAgeRating
      );
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

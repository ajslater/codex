<template>
  <v-table v-if="show">
    <tbody>
      <tr v-if="md.communityRating">
        <td class="key">Community Rating</td>
        <td>
          <MetadataText :value="md.communityRating" />
        </td>
      </tr>
      <tr v-if="md.criticalRating">
        <td class="key">Critical Rating</td>
        <td>
          <MetadataText :value="md.criticalRating" />
        </td>
      </tr>
      <tr v-if="md.ageRating">
        <td class="key">Age Rating</td>
        <td>
          <MetadataText :value="md.ageRating" />
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
        this.md?.communityRating || this.md?.criticRating || this.md?.ageRating
      );
    },
  },
};
</script>
<style scoped lang="scss">
@use "vuetify/styles/settings/variables" as vuetify;
@use "sass:map";
@use "./table";
@media #{map.get(vuetify.$display-breakpoints, 'sm-and-down')} {
  .key {
    font-size: x-small;
    padding-right: 3px !important;
  }
}
</style>

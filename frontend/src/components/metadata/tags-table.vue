<template>
  <v-table v-if="show">
    <tbody>
      <tr v-for="[key, { filter, tags }] of Object.entries(tagMap)" :key="key">
        <td class="key">{{ key }}</td>
        <td class="tags">
          <MetadataTags :filter="filter" :values="tags" />
        </td>
      </tr>
    </tbody>
  </v-table>
</template>

<script>
import MetadataTags from "@/components/metadata/metadata-tags.vue";

export default {
  name: "MetadataTagsTable",
  components: {
    MetadataTags,
  },
  props: {
    tagMap: {
      type: Object,
      required: true,
    },
  },
  computed: {
    show() {
      return Object.keys(this.tagMap).length > 0;
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
    font-size: small;
  }
}
</style>

<template>
  <v-table v-if="show">
    <tbody>
      <tr
        v-for="[key, { filter, tags, mainTags }] of Object.entries(tagMap)"
        :key="key"
      >
        <td class="key keyLink" v-if="keyMap && keyMap[key] && keyMap[key].url">
          <a href="keyMap[key].url"
            >{{ key }}<v-icon>{{ mdiOpenInNew }}</v-icon></a
          >
        </td>
        <td v-else class="key">{{ key }}</td>
        <td class="tags">
          <MetadataTags
            :filter="filter"
            :values="tags"
            :mainValues="mainTags"
          />
        </td>
      </tr>
    </tbody>
  </v-table>
</template>

<script>
import { mdiOpenInNew } from "@mdi/js";

import MetadataTags from "@/components/metadata/metadata-tags.vue";

export default {
  name: "MetadataTagsTable",
  components: {
    MetadataTags,
  },
  data() {
    return { mdiOpenInNew };
  },
  props: {
    keyMap: { type: Object, default: undefined },
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

.keyLink {
  color: rgb(var(--v-theme-primary-darken-1));
}

@media #{map.get(vuetify.$display-breakpoints, 'sm-and-down')} {
  .key {
    font-size: small;
  }
}
</style>

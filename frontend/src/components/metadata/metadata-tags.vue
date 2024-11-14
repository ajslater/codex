<template>
  <div v-if="items?.length > 0" class="tags">
    <div v-if="label" class="chipGroupLabel">
      {{ label }}
    </div>
    <div class="chips">
      <MetadataChip
        v-for="item in items"
        :filter="filter"
        :item="item"
        :key="`${filter}/${item.value}`"
      />
    </div>
  </div>
</template>

<script>
import { toVuetifyItems } from "@/api/v3/vuetify-items";
import MetadataChip from "@/components/metadata/metadata-chip.vue";

export default {
  name: "MetadataTags",
  components: { MetadataChip },
  props: {
    label: {
      type: String,
      default: "",
    },
    values: {
      type: Array,
      default() {
        return [];
      },
    },
    filter: {
      type: String,
      required: false,
      default: undefined,
    },
  },
  computed: {
    items() {
      return toVuetifyItems(this.values);
    },
  },
};
</script>

<style scoped lang="scss">
@use "vuetify/styles/settings/variables" as vuetify;
@use "sass:map";

.tags {
  padding: 5px;
}

.chipGroupLabel {
  font-size: 12px;
  color: rgb(var(--v-theme-textSecondary));
}
.chips * {
  margin-right: 5px;
}

@media #{map.get(vuetify.$display-breakpoints, 'sm-and-down')} {
  .chipGroupLabel {
    font-size: x-small !important;
  }
}
</style>

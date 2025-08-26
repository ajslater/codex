<template>
  <div v-if="items?.length > 0">
    <div v-if="label" class="chipGroupLabel">
      {{ label }}
    </div>
    <div>
      <MetadataChip
        v-for="item in mainItems"
        :key="`${filter}/${item.value}`"
        :filter="filter"
        :item="item"
        :main="true"
      />
      <MetadataChip
        v-for="item in items"
        :key="`${filter}/${item.value}`"
        :filter="filter"
        :item="item"
      />
    </div>
  </div>
</template>

<script>
import { mapActions } from "pinia";

import { toVuetifyItems } from "@/api/v3/vuetify-items";
import MetadataChip from "@/components/metadata/metadata-chip.vue";
import { useBrowserStore } from "@/stores/browser";

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
    mainValues: {
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
    mainItems() {
      return toVuetifyItems({ items: this.mainValues, sort: false });
    },
    items() {
      let items;
      if (this.filter === "universes") {
        items = this.fixUniverseTitles(this.values);
      } else {
        items = this.values;
      }
      return toVuetifyItems({ items, sort: false });
    },
  },
  methods: {
    ...mapActions(useBrowserStore, ["fixUniverseTitles"]),
  },
};
</script>

<style scoped lang="scss">
@use "vuetify/styles/settings/variables" as vuetify;
@use "sass:map";

.chipGroupLabel {
  font-size: 12px;
  color: rgb(var(--v-theme-textSecondary));
}

@media #{map.get(vuetify.$display-breakpoints, 'sm-and-down')} {
  .chipGroupLabel {
    font-size: x-small !important;
  }
}
</style>

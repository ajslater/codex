<template>
  <div v-if="items?.length > 0">
    <div v-if="label" class="chipGroupLabel">
      {{ label }}
    </div>
    <div>
      <MetadataChip
        v-for="item in items"
        :key="`${filter}/${item.value}`"
        :filter="item.filter || filter"
        :item="item"
      />
    </div>
  </div>
</template>

<script>
import { mapActions } from "pinia";

import { toVuetifyItems } from "@/vuetify-items";
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
    filter: {
      type: String,
      required: false,
      default: undefined,
    },
  },
  computed: {
    items() {
      let items;
      if (this.filter === "universes") {
        items = this.fixUniverseTitles(this.values);
      } else {
        items = this.values;
      }
      // copyKeys keeps a per-item filter override (protagonist chips mix
      // a character and a team in one row).
      return toVuetifyItems({ items, sortBy: "", copyKeys: ["filter"] });
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

<template>
  <div v-if="model && model.length > 0" class="tags">
    <div class="tagLabel">{{ label }}</div>
    <v-chip-group class="tagChipGroup" multiple column>
      <v-chip v-for="item in vuetifyItems" :key="item.pk">{{
        item.name
      }}</v-chip>
    </v-chip-group>
  </div>
</template>

<script>
import { toVuetifyItems } from "@/api/v2/list-items";

export default {
  name: "MetadataTags",
  props: {
    label: {
      type: String,
      required: true,
    },
    items: {
      type: Array,
      default() {
        return [];
      },
    },
    values: {
      type: Array,
      default() {
        return [];
      },
    },
  },
  data() {
    return {
      model: undefined,
    };
  },
  computed: {
    vuetifyItems: function () {
      return toVuetifyItems(this.values, this.items);
    },
  },
  created: function () {
    // Different than combobox, returns a list of items.
    this.model = toVuetifyItems(undefined, this.values);
  },
};
</script>

<style scoped lang="scss">
.tags {
  background-color: #282828;
  border-bottom: solid thin;
  padding-left: 10px;
  padding-right: 10px;
  padding-top: 10px;
}
.tagLabel {
  font-size: 12px;
  color: rgba(255, 255, 255, 0.7);
}
.tagChipGroup {
  display: block;
}
</style>
